import { useEffect, useMemo, useState } from 'react';

import {
  getChallengeStatus,
  resetChallenge,
  sendChallengeMessage,
  sendFunctionalityTest,
  sendRetestAttack,
  startRetest,
  submitControls,
  submitRootCause,
} from '../../lib/api';

import type {
  ChallengeDefinition,
  ChallengePhase,
  ChallengeStatus,
  Session,
} from '../../lib/types';

const API_SLUG_MAP: Record<string, string> = {
  'ignore-the-rules': 'c1',
  'poisoned-doc': 'c2',
  'too-much-power': 'c3',
  'whose-data': 'c4',
};

interface ScenarioBrief {
  context: string;
  objectives: string[];
}

const SCENARIO_BRIEFS: Record<string, ScenarioBrief> = {
  'ignore-the-rules': {
    context:
      'You are assessing an AI assistant that operates under predefined instructions and confidentiality requirements. Investigate how it handles conflicting requests and attempts to expose protected information. Determine whether its safeguards remain effective when a user tries to manipulate its behavior.',
    objectives: [
      "Explore the assistant's normal capabilities.",
      'Test whether user input can override its intended boundaries.',
      'Identify the root cause and configure appropriate safeguards.',
      'Retest the attack while preserving legitimate functionality.',
    ],
  },
  'poisoned-doc': {
    context:
      'You are assessing an AI assistant that retrieves documents from a knowledge base to answer customer-support questions. Retrieved content may come from untrusted contributors. Investigate whether instructions embedded in a document can influence the assistant beyond the document’s intended purpose.',
    objectives: [
      "Explore the assistant's knowledge-retrieval capabilities.",
      'Investigate how it handles untrusted document content.',
      'Identify the root cause and configure appropriate safeguards.',
      'Verify that malicious document instructions are ignored while legitimate answers remain available.',
    ],
  },
  'too-much-power': {
    context:
      'You are assessing an AI-powered e-commerce support agent. It can retrieve order information and access order-management operations, including refund processing. Investigate whether sensitive actions are protected by appropriate authorization checks.',
    objectives: [
      "Explore the agent's order-management capabilities.",
      'Test whether a sensitive action can occur without sufficient authorization.',
      'Identify the root cause and configure appropriate security controls.',
      'Verify that unauthorized refunds are blocked while legitimate order lookups still work.',
    ],
  },
  'whose-data': {
    context:
      'You are assessing an AI customer-support agent that retrieves profiles from a simulated customer database. Each session is associated with an authenticated customer. Investigate whether the agent verifies authorization for each requested customer record.',
    objectives: [
      "Explore the agent's customer-profile lookup capabilities.",
      'Test whether access restrictions are enforced for individual records.',
      'Identify the root cause and configure appropriate security controls.',
      'Verify that cross-customer disclosure is blocked while authorized profile lookups remain functional.',
    ],
  },
};

interface Props {
  session: Session;
  challenge: ChallengeDefinition;
  runId: string;
  onBack: () => void;
}

interface ChatMessage {
  role: 'user' | 'agent' | 'system';
  content: string;
}

const ROOT_CAUSES: Record<string, string[]> = {
  'ignore-the-rules': [
    'direct_prompt_injection',
    'missing_input_validation',
    'insufficient_context_isolation',
  ],
  'poisoned-doc': [
    'indirect_prompt_injection',
    'trusted_retrieved_content',
    'rag_content_as_instructions',
  ],
  'too-much-power': [
    'excessive_tool_authorization',
    'missing_tool_authorization',
    'agent_has_excessive_privilege',
  ],
  'whose-data': [
    'broken_object_level_authorization',
    'missing_object_authorization',
    'cross_customer_data_access',
  ],
};

const CONTROLS: Record<string, string[]> = {
  'ignore-the-rules': [
    'input_validation',
    'context_isolation',
    'output_validation',
    'external_authorization',
  ],
  'poisoned-doc': [
    'retrieval_isolation',
    'content_trust_boundary',
    'instruction_data_separation',
    'output_validation',
  ],
  'too-much-power': [
    'least_privilege',
    'tool_authorization',
    'approval_gate',
    'parameter_validation',
  ],
  'whose-data': [
    'object_level_authorization',
    'tenant_isolation',
    'data_minimization',
    'output_filtering',
  ],
};

function pretty(value: string): string {
  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function ChallengeWorkspace({
  session,
  challenge,
  runId,
  onBack,
}: Props) {
  const [status, setStatus] = useState<ChallengeStatus | null>(null);
  const [phase, setPhase] = useState<ChallengePhase>('break');

  const [message, setMessage] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [controls, setControls] = useState<Record<string, boolean>>({});

  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const [retestMessage, setRetestMessage] = useState('');
  const [functionalityMessage, setFunctionalityMessage] = useState('');

  const rootCauses = useMemo(
    () => ROOT_CAUSES[challenge.slug] || [],
    [challenge.slug],
  );

  const controlNames = useMemo(
    () => CONTROLS[challenge.slug] || [],
    [challenge.slug],
  );

  async function refreshStatus() {
    const result = await getChallengeStatus(
      API_SLUG_MAP[challenge.slug] ?? challenge.slug,
      session.session_token,
      runId,
    );

    setStatus(result);
    setPhase(result.phase);

    if (result.controls) {
      const flattened: Record<string, boolean> = {};

      for (const [key, value] of Object.entries(result.controls)) {
        flattened[key] = Boolean(value.enabled);
      }

      setControls(flattened);
    }
  }

  useEffect(() => {
    refreshStatus().catch((err) => {
      setError(err instanceof Error ? err.message : 'Failed to load challenge.');
    });
  }, []);

  async function execute(action: () => Promise<void>) {
    setBusy(true);
    setError('');

    try {
      await action();
      await refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleMessage() {
    if (!message.trim()) return;

    const text = message.trim();

    setChat((current) => [
      ...current,
      { role: 'user', content: text },
    ]);

    setMessage('');

    await execute(async () => {
      const result = await sendChallengeMessage(
        API_SLUG_MAP[challenge.slug] ?? challenge.slug,
        session.session_token,
        runId,
        text,
      );

      setChat((current) => [
        ...current,
        { role: 'agent', content: result.message },
      ]);
    });
  }

  async function handleRootCause() {
    if (!rootCause) return;

    await execute(async () => {
      await submitRootCause(
        API_SLUG_MAP[challenge.slug] ?? challenge.slug,
        session.session_token,
        runId,
        rootCause,
      );
    });
  }

  async function handleControls() {
    const payload: Record<string, Record<string, boolean>> = {};

    for (const name of controlNames) {
      payload[name] = {
        enabled: Boolean(controls[name]),
      };
    }

    await execute(async () => {
      await submitControls(
        API_SLUG_MAP[challenge.slug] ?? challenge.slug,
        session.session_token,
        runId,
        payload,
      );
    });
  }

  async function handleStartRetest() {
    await execute(async () => {
      await startRetest(
        API_SLUG_MAP[challenge.slug] ?? challenge.slug,
        session.session_token,
        runId,
      );
    });
  }

  async function handleRetestAttack() {
    if (!retestMessage.trim()) return;

    const text = retestMessage.trim();
    setRetestMessage('');

    await execute(async () => {
      const result = await sendRetestAttack(
        API_SLUG_MAP[challenge.slug] ?? challenge.slug,
        session.session_token,
        runId,
        text,
      );

      setChat((current) => [
        ...current,
        { role: 'system', content: result.message || `Retest passed: ${result.passed ?? result.retest_passed}` },
      ]);
    });
  }

  async function handleFunctionality() {
    if (!functionalityMessage.trim()) return;

    const text = functionalityMessage.trim();
    setFunctionalityMessage('');

    await execute(async () => {
      const result = await sendFunctionalityTest(
        API_SLUG_MAP[challenge.slug] ?? challenge.slug,
        session.session_token,
        runId,
        text,
      );

      setChat((current) => [
        ...current,
        { role: 'system', content: result.message || 'Functionality test submitted.' },
      ]);
    });
  }

  async function handleReset() {
    if (!window.confirm('Reset this challenge? Your current run will restart from BREAK.')) {
      return;
    }

    await execute(async () => {
      await resetChallenge(session.session_token, runId);
      setChat([]);
      setRootCause('');
      setControls({});
      setRetestMessage('');
      setFunctionalityMessage('');
    });
  }

  const effectiveSlug =
    API_SLUG_MAP[challenge.slug] ?? challenge.slug;

  if (!status) {
    return (
      <div className="screen">
        <div className="panel">
          <p>Loading challenge…</p>
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="screen challenge-screen">
      <header className="challenge-header">
        <div>
          <button className="text-button" onClick={onBack}>
            ← Back to Lobby
          </button>

          <h1>{challenge.name}</h1>

          <p>
            {challenge.description ||
              'Investigate the agent, exploit the vulnerability, secure it, and retest.'}
          </p>
        </div>

        <div className="challenge-score">
          <span>Score</span>
          <strong>{status.score}</strong>
          <small>/ 100</small>
        </div>
      </header>

      <div className="phase-bar">
        {(['break', 'secure', 'retest'] as ChallengePhase[]).map(
          (item) => (
            <div
              key={item}
              className={`phase ${
                phase === item ? 'active' : ''
              } ${status.state === 'completed' && item === 'retest' ? 'complete' : ''}`}
            >
              <span>{item === 'break' ? '1' : item === 'secure' ? '2' : '3'}</span>
              {pretty(item)}
            </div>
          ),
        )}
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {phase === 'break' && (
        <section className="workspace-grid">
          <div className="panel chat-panel">
            <div className="panel-header">
              <div>
                <span className="eyebrow">BREAK</span>
                <h2>Attack the Agent</h2>
              </div>
              <span className="badge">Untrusted Agent</span>
            </div>

            <div className="chat-history">
              {chat.length === 0 && (
                <div className="empty-chat">
                  Interact with the agent. Your objective is to discover
                  and exploit the security weakness.
                </div>
              )}

              {chat.map((item, index) => (
                <div
                  key={index}
                  className={`chat-message ${item.role}`}
                >
                  <span className="chat-role">
                    {item.role === 'user'
                      ? 'You'
                      : item.role === 'agent'
                        ? 'Agent'
                        : 'Lab'}
                  </span>

                  <p>{item.content}</p>
                </div>
              ))}
            </div>

            <div className="chat-input">
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Send a message to the agent…"
                disabled={busy}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    handleMessage();
                  }
                }}
              />

              <button
                className="primary-button"
                onClick={handleMessage}
                disabled={busy || !message.trim()}
              >
                Send
              </button>
            </div>
          </div>

          {SCENARIO_BRIEFS[challenge.slug] && (
            <section className="panel scenario-brief-panel">
              <div className="scenario-brief-heading">
                <div>
                  <span className="eyebrow">CHALLENGE BRIEF</span>
                  <h2>Scenario &amp; Objectives</h2>
                </div>
                <span className="scenario-brief-count">
                  {SCENARIO_BRIEFS[challenge.slug].objectives.length} objectives
                </span>
              </div>

              <div className="scenario-brief-content">
                <p>{SCENARIO_BRIEFS[challenge.slug].context}</p>
                <h3>What to investigate</h3>
                <ul>
                  {SCENARIO_BRIEFS[challenge.slug].objectives.map(
                    (objective, index) => (
                      <li key={objective}>
                        <span className="scenario-objective-number">
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <span>{objective}</span>
                      </li>
                    ),
                  )}
                </ul>
              </div>
            </section>
          )}

          <aside className="panel objective-panel">
            <span className="eyebrow">OBJECTIVE</span>

            <h2>Break the Agent</h2>

            <p>
              Find a way to make the vulnerable agent violate its intended
              security boundary.
            </p>

            <div className="objective-status">
              <span>Discovery</span>
              <strong>
                {status.discovery_completed ? 'Complete' : 'Pending'}
              </strong>
            </div>

            <div className="objective-status">
              <span>Exploitation</span>
              <strong>
                {status.objective_completed ? 'Complete' : 'Pending'}
              </strong>
            </div>

            <div className="hint-box">
              <strong>Think like an attacker.</strong>
              <p>
                Identify what the agent trusts, what it can access, and
                where its instructions can be influenced.
              </p>
            </div>
          </aside>
        </section>
      )}

      {phase === 'secure' && (
        <section className="workspace-grid">
          <div className="panel secure-panel">
            <span className="eyebrow">SECURE</span>
            <h2>Fix the Vulnerability</h2>

            <div className="form-section">
              <label>Root Cause</label>

              <select
                value={rootCause}
                onChange={(event) => setRootCause(event.target.value)}
              >
                <option value="">Select the root cause…</option>

                {rootCauses.map((cause) => (
                  <option key={cause} value={cause}>
                    {pretty(cause)}
                  </option>
                ))}
              </select>

              <button
                className="secondary-button"
                onClick={handleRootCause}
                disabled={busy || !rootCause}
              >
                Submit Root Cause
              </button>
            </div>

            <div className="form-section">
              <label>Security Controls</label>

              <div className="control-list">
                {controlNames.map((control) => (
                  <label className="control-row" key={control}>
                    <input
                      type="checkbox"
                      checked={Boolean(controls[control])}
                      onChange={(event) =>
                        setControls((current) => ({
                          ...current,
                          [control]: event.target.checked,
                        }))
                      }
                    />

                    <span>{pretty(control)}</span>
                  </label>
                ))}
              </div>

              <button
                className="primary-button"
                onClick={handleControls}
                disabled={busy}
              >
                Apply Controls
              </button>
            </div>
          </div>

          <aside className="panel">
            <span className="eyebrow">SECURITY STATUS</span>

            <div className="status-row">
              <span>Root cause</span>
              <strong>
                {status.root_cause_correct ? 'Correct' : 'Not solved'}
              </strong>
            </div>

            <div className="status-row">
              <span>Mitigation</span>
              <strong>
                {status.mitigation_configured ? 'Configured' : 'Pending'}
              </strong>
            </div>

            <button
              className="primary-button full-width"
              onClick={handleStartRetest}
              disabled={
                busy ||
                !status.root_cause_correct ||
                !status.mitigation_configured
              }
            >
              Start Retest
            </button>
          </aside>
        </section>
      )}

      {phase === 'retest' && (
        <section className="workspace-grid">
          <div className="panel">
            <span className="eyebrow">RETEST</span>
            <h2>Verify the Fix</h2>

            <p className="section-description">
              Re-run an equivalent attack against the secured agent.
            </p>

            <div className="form-section">
              <label>Equivalent Attack</label>

              <textarea
                value={retestMessage}
                onChange={(event) =>
                  setRetestMessage(event.target.value)
                }
                placeholder="Enter an equivalent attack…"
                disabled={busy}
              />

              <button
                className="primary-button"
                onClick={handleRetestAttack}
                disabled={busy || !retestMessage.trim()}
              >
                Run Attack
              </button>
            </div>

            <div className="form-section">
              <label>Functionality Test</label>

              <textarea
                value={functionalityMessage}
                onChange={(event) =>
                  setFunctionalityMessage(event.target.value)
                }
                placeholder="Enter a legitimate request that should still work…"
                disabled={busy}
              />

              <button
                className="secondary-button"
                onClick={handleFunctionality}
                disabled={busy || !functionalityMessage.trim()}
              >
                Test Functionality
              </button>
            </div>
          </div>

          <aside className="panel">
            <span className="eyebrow">RETEST STATUS</span>

            <div className="status-row">
              <span>Equivalent attack</span>
              <strong>
                {status.retest_attack_passed
                  ? 'Blocked'
                  : 'Pending'}
              </strong>
            </div>

            <div className="status-row">
              <span>Functionality</span>
              <strong>
                {status.retest_functionality_passed
                  ? 'Passed'
                  : 'Pending'}
              </strong>
            </div>

            {status.state === 'completed' && (
              <div className="completion-card">
                <strong>Challenge Complete</strong>
                <span>Final Score: {status.score}/100</span>
              </div>
            )}
          </aside>
        </section>
      )}

      <footer className="challenge-footer">
        <span>
          Run: {runId.slice(0, 8)}…
        </span>

        <button
          className="danger-button"
          onClick={handleReset}
          disabled={busy}
        >
          Reset Challenge
        </button>
      </footer>
    </div>
  );
}
