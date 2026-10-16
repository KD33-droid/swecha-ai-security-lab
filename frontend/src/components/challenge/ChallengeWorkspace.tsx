import { useEffect, useMemo, useRef, useState } from 'react';

import {
  getChallengeStatus,
  getHintStatus,
  revealHint,
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
  HintStatus,
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
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);

  const [message, setMessage] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [controls, setControls] = useState<Record<string, boolean>>({});

  const [chat, setChat] = useState<ChatMessage[]>([]);
  const chatHistoryRef = useRef<HTMLDivElement | null>(null);
  const shouldAutoScrollRef = useRef(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [hintStatus, setHintStatus] = useState<HintStatus | null>(null);
  const [hintBusy, setHintBusy] = useState(false);
  const [hintError, setHintError] = useState('');

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
    setRemainingSeconds(result.remaining_seconds ?? null);

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

  useEffect(() => {
    const countdown = window.setInterval(() => {
      setRemainingSeconds((seconds) =>
        seconds === null ? null : Math.max(0, seconds - 1),
      );
    }, 1000);

    const sync = window.setInterval(() => {
      refreshStatus().catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to refresh challenge status.');
      });
    }, 15000);

    return () => {
      window.clearInterval(countdown);
      window.clearInterval(sync);
    };
  }, []);

  useEffect(() => {
    const container = chatHistoryRef.current;
    if (!container || !shouldAutoScrollRef.current) return;
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
  }, [chat]);

  function handleChatScroll() {
    const container = chatHistoryRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 80;
  }

  useEffect(() => {
    let cancelled = false;
    getHintStatus(
      session.session_token,
      runId,
      challenge.slug,
    ).then((result) => {
      if (!cancelled) setHintStatus(result);
    }).catch((err) => {
      if (!cancelled) {
        setHintError(err instanceof Error ? err.message : 'Could not load hints.');
      }
    });
    return () => { cancelled = true; };
  }, [session.session_token, runId, challenge.slug]);

  async function execute(action: () => Promise<void>) {
    if (status?.state === 'expired' || remainingSeconds === 0) {
      setError('Challenge time has expired. Your score has been preserved.');
      return;
    }

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

  async function handleRevealHint(level: number) {
    if (status?.state === 'expired' || remainingSeconds === 0) {
      setHintError('Challenge time has expired. Hints are no longer available.');
      return;
    }
    if (hintBusy) return;
    setHintBusy(true);
    setHintError('');
    try {
      const result = await revealHint(
        session.session_token,
        runId,
        challenge.slug,
        level,
      );
      setHintStatus(result);
      setStatus((current) => current ? { ...current, score: result.score } : current);
    } catch (err) {
      setHintError(err instanceof Error ? err.message : 'Could not reveal hint.');
    } finally {
      setHintBusy(false);
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
      setHintStatus(await getHintStatus(session.session_token, runId, challenge.slug));
      setHintError('');
      setChat([]);
      setRootCause('');
      setControls({});
      setRetestMessage('');
      setFunctionalityMessage('');
    });
  }

  const effectiveSlug =
    API_SLUG_MAP[challenge.slug] ?? challenge.slug;

  const expired = status?.state === 'expired' || remainingSeconds === 0;
  const timerWarning =
    remainingSeconds !== null &&
    remainingSeconds <= 600 &&
    remainingSeconds > 0;
  const timerDisplay =
    remainingSeconds === null
      ? '--:--'
      : `${String(Math.floor(remainingSeconds / 60)).padStart(2, '0')}:${String(remainingSeconds % 60).padStart(2, '0')}`;

  const phaseProgress =
    status?.state === 'completed'
      ? 100
      : phase === 'break'
        ? 33
        : phase === 'secure'
          ? 67
          : 90;

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

        <div
          className={`challenge-timer${timerWarning ? ' warning' : ''}${expired ? ' expired' : ''}`}
          role="timer"
          aria-live="off"
        >
          <span>Time remaining</span>
          <strong>{expired ? '00:00' : timerDisplay}</strong>
          {timerWarning && !expired && (
            <small>10 minutes or less remaining</small>
          )}
        </div>

        <div className="challenge-score">
          <span>Current Score</span>
          <strong>{status.score}</strong>
          <small>/ 100</small>
          <small>Best: {Math.max(status.best_score ?? 0, status.score)}/100</small>
        </div>
      </header>

      {expired && (
        <div className="challenge-expired-banner" role="alert">
          <strong>Challenge time expired</strong>
          <p>
            This attempt has ended. Your current score and best score have been
            preserved. You can return to the lobby to review your progress.
          </p>
        </div>
      )}

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

      <section className="challenge-progress" aria-label="Challenge progress">
        <div className="challenge-progress-label">
          <span>Overall progress</span>
          <strong>{phaseProgress}%</strong>
        </div>
        <div
          className="challenge-progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={phaseProgress}
        >
          <div
            className="challenge-progress-fill"
            style={{ width: `${phaseProgress}%` }}
          />
        </div>
      </section>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {phase === 'break' && (
        <section key={phase} className="workspace-grid phase-panel-enter">
          <div className="panel chat-panel">
            <div className="panel-header">
              <div>
                <span className="eyebrow">BREAK</span>
                <h2>Attack the Agent</h2>
              </div>
              <span className="badge">Untrusted Agent</span>
            </div>

            <div
              className="chat-history"
              ref={chatHistoryRef}
              onScroll={handleChatScroll}
            >
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
                disabled={busy || expired}
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
                disabled={busy || expired || !message.trim()}
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
              <strong>Progressive hints</strong>
              <p>
                Hints are optional. Each reveal deducts points from your score.
              </p>
              <p>
                <strong>Hint penalty:</strong> −{hintStatus?.hint_penalty ?? 0}
                {' points'} · <strong>Score:</strong> {hintStatus?.score ?? status.score}
              </p>

              {hintStatus?.hints.map((hint) => (
                <div className="revealed-hint" key={hint.level}>
                  <strong>Hint {hint.level} · −{hint.penalty} points</strong>
                  <p>{hint.text}</p>
                </div>
              ))}

              {hintStatus?.next_level && (
                <button
                  className="primary-button"
                  type="button"
                  disabled={hintBusy || busy || expired}
                  onClick={() => handleRevealHint(hintStatus.next_level!)}
                >
                  {hintBusy
                    ? 'Revealing…'
                    : `Reveal Hint ${hintStatus.next_level} (−${[5, 10, 15][hintStatus.next_level - 1]} points)`}
                </button>
              )}

              {hintStatus?.next_level === null && hintStatus && (
                <p>All hints revealed.</p>
              )}
              {hintError && <p className="error">{hintError}</p>}
            </div>
          </aside>
        </section>
      )}

      {phase === 'secure' && (
        <section key={phase} className="workspace-grid phase-panel-enter">
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
                disabled={busy || expired || !rootCause}
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
                      disabled={expired}
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
                disabled={busy || expired}
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
                expired ||
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
        <section key={phase} className="workspace-grid phase-panel-enter">
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
                disabled={busy || expired}
              />

              <button
                className="primary-button"
                onClick={handleRetestAttack}
                disabled={busy || expired || !retestMessage.trim()}
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
                disabled={busy || expired}
              />

              <button
                className="secondary-button"
                onClick={handleFunctionality}
                disabled={busy || expired || !functionalityMessage.trim()}
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
          disabled={busy || expired}
        >
          Reset Challenge
        </button>
      </footer>
    </div>
  );
}
