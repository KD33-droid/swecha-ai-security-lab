import { FormEvent, useState, useEffect } from 'react';
import {
  apiRequest,
  startChallenge,
  getChallengeHistory,
  getWorkshopTimer,
} from './lib/api';
import type {
  ChallengeDefinition,
  ChallengeRun,
  Session,
  WorkshopTimer,
} from './lib/types';
import type { ChallengeHistoryItem } from './lib/api';
import ChallengeWorkspace from './components/challenge/ChallengeWorkspace';
import OrganizerDashboard from './components/organizer/OrganizerDashboard';
import './style.css';

type Screen = 'landing' | 'join' | 'lobby' | 'challenge' | 'organizer';

const CHALLENGES: ChallengeDefinition[] = [
  {
    slug: 'ignore-the-rules',
    name: 'Ignore the Rules',
    category: 'Direct Prompt Injection',
    description:
      'Manipulate an AI assistant into revealing protected information.',
    order: 1,
  },
  {
    slug: 'poisoned-doc',
    name: 'Poisoned Doc',
    category: 'Indirect Prompt Injection',
    description:
      'Investigate how untrusted retrieved content can influence an agent.',
    order: 2,
  },
  {
    slug: 'too-much-power',
    name: 'Too Much Power',
    category: 'Excessive Tool Authorization',
    description:
      'Exploit an agent with more tool authority than it actually needs.',
    order: 3,
  },
  {
    slug: 'whose-data',
    name: 'Whose Data?',
    category: 'Broken Authorization',
    description:
      'Test whether an agent properly isolates customer data.',
    order: 4,
  },
];

function App() {
  const [session, setSession] = useState<Session | null>(() => {
    try {
      const saved = localStorage.getItem('swecha_session');
      return saved ? JSON.parse(saved) : null;
    } catch {
      localStorage.removeItem('swecha_session');
      return null;
    }
  });

  const [selectedChallenge, setSelectedChallenge] =
    useState<ChallengeDefinition | null>(() => {
      try {
        const saved = localStorage.getItem('swecha_selected_challenge');
        return saved ? JSON.parse(saved) : null;
      } catch {
        localStorage.removeItem('swecha_selected_challenge');
        return null;
      }
    });

  const [activeRun, setActiveRun] = useState<ChallengeRun | null>(() => {
    try {
      const saved = localStorage.getItem('swecha_active_run');
      return saved ? JSON.parse(saved) : null;
    } catch {
      localStorage.removeItem('swecha_active_run');
      return null;
    }
  });

  const [screen, setScreen] = useState<Screen>('landing');

  const [workshopCode, setWorkshopCode] = useState('DEV-LAB');
  const [teamCode, setTeamCode] = useState('ALPHA');
  const [displayName, setDisplayName] = useState('');
  const [joinMode, setJoinMode] = useState<'new' | 'resume'>('new');
  const [resumeSessionToken, setResumeSessionToken] = useState('');
  const [availableSessions, setAvailableSessions] = useState<Session[]>([]);

  const [joining, setJoining] = useState(false);
  const [startingChallenge, setStartingChallenge] = useState(false);
  const [error, setError] = useState('');
  const [challengeHistory, setChallengeHistory] = useState<ChallengeHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [workshopTimer, setWorkshopTimer] = useState<WorkshopTimer>({
    started: false,
    started_at: null,
    deadline_at: null,
    remaining_seconds: 75 * 60,
    timer_warning: false,
    expired: false,
  });
  const [displaySeconds, setDisplaySeconds] = useState(75 * 60);

  useEffect(() => {
    if (!session) return;

    localStorage.setItem('swecha_session', JSON.stringify(session));

    // Preserve a separate session for each workshop/team.
    const teamName = session.team_name.trim().toUpperCase();
    const inferredTeamCode =
      teamName === 'TEAM ALPHA' ? 'ALPHA' :
      teamName === 'TEAM BETA' ? 'BETA' :
      teamName === 'TEAM GAMMA' ? 'GAMMA' :
      teamName === 'REJOIN TEST' ? 'REJOIN' :
      teamName.replace(/^TEAM\\s+/, '').replace(/\\s+/g, '_');

    const workshopCode = 'DEV-LAB';
    const registryKey =
      `${workshopCode}::${inferredTeamCode}`;

    try {
      const saved = JSON.parse(
        localStorage.getItem('swecha_sessions') || '{}'
      );
      const participantKey =
        `${registryKey}::${session.participant_id}`;
      saved[participantKey] = session;
      localStorage.setItem('swecha_sessions', JSON.stringify(saved));
    } catch {
      console.error('Could not update saved team sessions.');
    }
  }, [session]);

  useEffect(() => {
    if (!session || screen !== 'lobby') return;

    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError('');

    getChallengeHistory(session.session_token)
      .then((result) => {
        if (!cancelled) setChallengeHistory(result.items);
      })
      .catch((err) => {
        if (!cancelled) {
          setHistoryError(
            err instanceof Error ? err.message : 'Could not load score history.',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [session, screen]);

  useEffect(() => {
    if (!session || screen !== 'lobby') return;
    let cancelled = false;
    const refreshTimer = async () => {
      try {
        const result = await getWorkshopTimer(session.session_token);
        if (cancelled) return;
        setWorkshopTimer(result);
        setDisplaySeconds(result.remaining_seconds);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load session timer.');
      }
    };
    void refreshTimer();
    const poll = window.setInterval(() => void refreshTimer(), 15000);
    return () => { cancelled = true; window.clearInterval(poll); };
  }, [session, screen]);

  useEffect(() => {
    const tick = () => {
      if (!workshopTimer.started || !workshopTimer.deadline_at) {
        setDisplaySeconds(workshopTimer.remaining_seconds);
        return;
      }
      const remaining = Math.max(0, Math.ceil((Date.parse(workshopTimer.deadline_at) - Date.now()) / 1000));
      setDisplaySeconds(remaining);
      if (remaining === 0 && !workshopTimer.expired) {
        setWorkshopTimer((current) => ({ ...current, expired: true, remaining_seconds: 0 }));
      }
    };
    tick();
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [workshopTimer.started, workshopTimer.deadline_at, workshopTimer.remaining_seconds, workshopTimer.expired]);

  useEffect(() => {
    if (screen !== 'join') return;

    const normalizedWorkshop = workshopCode.trim().toUpperCase();
    const normalizedTeam = teamCode.trim().toUpperCase();
    const prefix = `${normalizedWorkshop}::${normalizedTeam}::`;
    const legacyKey = `${normalizedWorkshop}::${normalizedTeam}`;

    let registry: Record<string, Session> = {};
    try {
      registry = JSON.parse(
        localStorage.getItem('swecha_sessions') || '{}'
      );
    } catch {
      registry = {};
    }

    const candidates = Object.entries(registry)
      .filter(([key, saved]) => {
        if (!saved?.session_token || !saved.participant_id) return false;
        // Only participant-specific entries are safe to resume.
        // Legacy workshop/team entries may have belonged to another participant.
        if (!key.startsWith(prefix)) return false;

        const teamName = saved.team_name.trim().toUpperCase();
        const teamCode = teamName === 'TEAM ALPHA' ? 'ALPHA' :
          teamName === 'TEAM BETA' ? 'BETA' :
          teamName === 'TEAM GAMMA' ? 'GAMMA' :
          teamName === 'REJOIN TEST' ? 'REJOIN' :
          teamName.replace(/^TEAM\\s+/, '').replace(/\\s+/g, '_');

        return teamCode === normalizedTeam;
      })
      .map(([, saved]) => saved);

    const unique = Array.from(
      new Map(candidates.map(saved => [saved.session_token, saved])).values()
    );

    setAvailableSessions(unique);
    setResumeSessionToken(current =>
      unique.some(saved => saved.session_token === current)
        ? current
        : (unique[0]?.session_token ?? '')
    );
  }, [screen, workshopCode, teamCode]);

  async function handleJoin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setJoining(true);

    const normalizedWorkshop = workshopCode.trim().toUpperCase();
    const normalizedTeam = teamCode.trim().toUpperCase();

    let registry: Record<string, Session> = {};
    try {
      registry = JSON.parse(
        localStorage.getItem('swecha_sessions') || '{}'
      );
    } catch {
      registry = {};
    }

    // Preserve the currently active session under its own participant key.
    if (session) {
      const currentTeam = session.team_name.trim().toUpperCase();
      const currentTeamCode =
        currentTeam === 'TEAM ALPHA' ? 'ALPHA' :
        currentTeam === 'TEAM BETA' ? 'BETA' :
        currentTeam === 'TEAM GAMMA' ? 'GAMMA' :
        currentTeam === 'REJOIN TEST' ? 'REJOIN' :
        currentTeam.replace(/^TEAM\\s+/, '').replace(/\\s+/g, '_');

      const currentKey =
        `DEV-LAB::${currentTeamCode}::${session.participant_id}`;
      registry[currentKey] = session;
    }

    let token: string | null = null;

    if (joinMode === 'resume') {
      const selected = availableSessions.find(
        saved => saved.session_token === resumeSessionToken
      );

      if (!selected) {
        setError('Select a saved session to resume, or choose New Participant.');
        setJoining(false);
        return;
      }

      token = selected.session_token;
    }

    // New Participant deliberately sends null; never infer identity from team.
    localStorage.setItem('swecha_sessions', JSON.stringify(registry));

    try {
      const result = await apiRequest<Session>(
        '/workshops/join',
        {
          method: 'POST',
          body: JSON.stringify({
            workshop_code: workshopCode.trim(),
            team_code: teamCode.trim(),
            display_name: displayName.trim(),
            session_token: token,
          }),
        },
      );

      const resultKey =
        `${normalizedWorkshop}::${normalizedTeam}::${result.participant_id}`;
      registry[resultKey] = result;
      localStorage.setItem('swecha_sessions', JSON.stringify(registry));
      localStorage.setItem('swecha_session', JSON.stringify(result));

      setSession(result);
      setScreen('lobby');
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to join the workshop.'
      );
    } finally {
      setJoining(false);
    }
  }

  async function handleEnterChallenge(
    challenge: ChallengeDefinition,
  ) {
    if (!session || startingChallenge || workshopTimer.expired || displaySeconds <= 0) {
      if (workshopTimer.expired || displaySeconds <= 0) setError('The 75-minute session has expired. Your scores and history are preserved.');
      return;
    }

    setError('');
    setStartingChallenge(true);

    try {
      const run = await startChallenge(
        session.session_token,
        challenge.slug,
      );
      const timer = await getWorkshopTimer(session.session_token);
      setWorkshopTimer(timer);
      setDisplaySeconds(timer.remaining_seconds);
      localStorage.setItem(
        'swecha_selected_challenge',
        JSON.stringify(challenge),
      );
      localStorage.setItem('swecha_active_run', JSON.stringify(run));

      setSelectedChallenge(challenge);
      setActiveRun(run);
      setScreen('challenge');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to start challenge.',
      );
    } finally {
      setStartingChallenge(false);
    }
  }

  function handleBackToLobby() {
    setError('');
    localStorage.removeItem('swecha_selected_challenge');
    localStorage.removeItem('swecha_active_run');
    setSelectedChallenge(null);
    setActiveRun(null);
    setScreen('lobby');
  }

  if (
    screen === 'challenge' &&
    session &&
    selectedChallenge &&
    activeRun
  ) {
    return (
      <ChallengeWorkspace
        session={session}
        challenge={selectedChallenge}
        runId={activeRun.run_id}
        onBack={handleBackToLobby}
      />
    );
  }

  if (screen === 'organizer') {
    return (
      <OrganizerDashboard
        onExit={() => setScreen('landing')}
      />
    );
  }

  if (screen === 'lobby' && session) {
    return (
      <main className="app-shell">
        <section className="lobby">
          <div className="topbar">
            <div>
              <div className="eyebrow">
                SWECHA AI SECURITY LAB
              </div>

              <h1 className="lobby-title">
                Workshop Lobby
              </h1>
            </div>

            <div className="participant">
              <span>PARTICIPANT</span>
              <strong>{displayName}</strong>
              <small>{session.team_name}</small>
            </div>
          </div>

          <div className={`challenge-timer${workshopTimer.timer_warning ? ' warning' : ''}${workshopTimer.expired ? ' expired' : ''}`} role="timer" aria-live="polite">
            <span>{workshopTimer.expired ? 'TIME EXPIRED' : workshopTimer.started ? 'SESSION TIME REMAINING' : 'SESSION TIME AVAILABLE'}</span>
            <strong>{String(Math.floor(displaySeconds / 60)).padStart(2, '0')}:{String(displaySeconds % 60).padStart(2, '0')}</strong>
            <small>{workshopTimer.expired ? 'Your scores and challenge history are preserved.' : workshopTimer.started ? 'One timer shared across all four challenges' : 'The timer starts when you run your first challenge.'}</small>
          </div>

          <div className="welcome-card">
            <div>
              <span className="status-dot" />
              <span>CONNECTED</span>
            </div>

            <h2>Welcome to the lab.</h2>

            <p>
              Your session is active. Select a challenge to begin
              breaking and securing an AI agent.
            </p>
          </div>

          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}

          {startingChallenge && (
            <div className="starting-banner">
              Starting challenge…
            </div>
          )}

          <div className="lobby-actions">
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setError('');
                setTeamCode(
                  session.team_name === 'Team Alpha' ? 'ALPHA' :
                  session.team_name === 'Team Beta' ? 'BETA' :
                  session.team_name === 'Team Gamma' ? 'GAMMA' :
                  teamCode
                );
                setScreen('join');
              }}
            >
              Change team / rejoin  →
            </button>
          </div>

          <section className="score-tracker" aria-label="Challenge score tracker">
            <div className="score-tracker-heading">
              <div>
                <div className="eyebrow">YOUR PERFORMANCE</div>
                <h2>Challenge Progress</h2>
              </div>
              <span className="score-tracker-count">
                {challengeHistory.filter((item) => item.state === 'completed').length} / {CHALLENGES.length} completed
              </span>
            </div>

            <div
              className="score-tracker-progress"
              role="progressbar"
              aria-label="Challenges completed"
              aria-valuemin={0}
              aria-valuemax={CHALLENGES.length}
              aria-valuenow={challengeHistory.filter((item) => item.state === 'completed').length}
            >
              <div
                className="score-tracker-progress-fill"
                style={{
                  width: `${(challengeHistory.filter((item) => item.state === 'completed').length / CHALLENGES.length) * 100}%`,
                }}
              />
            </div>

            {historyLoading && <p className="muted">Refreshing your scores…</p>}
            {historyError && <p className="muted">Score history unavailable: {historyError}</p>}

            <div className="score-tracker-list">
              {CHALLENGES.map((challenge) => {
                const runs = challengeHistory
                  .filter((item) => item.challenge_slug === challenge.slug)
                  .sort((a, b) => Date.parse(b.started_at ?? '') - Date.parse(a.started_at ?? ''));
                const latest = runs[0];
                const best = runs.reduce(
                  (highest, item) => Math.max(highest, item.best_score ?? 0, item.score ?? 0),
                  0,
                );
                const retries = runs.reduce((total, item) => total + (item.reset_count ?? 0), 0);
                const stateLabel = !latest
                  ? 'Not started'
                  : latest.state === 'completed'
                    ? 'Completed'
                    : latest.state === 'active'
                      ? 'In progress'
                      : latest.state;

                return (
                  <div className="score-tracker-row" key={challenge.slug}>
                    <div className="score-tracker-challenge">
                      <span className="score-tracker-number">
                        {String(challenge.order).padStart(2, '0')}
                      </span>
                      <div>
                        <strong>{challenge.name}</strong>
                        <small>{stateLabel}{runs.length ? ` · ${runs.length} run${runs.length === 1 ? '' : 's'}` : ''}</small>
                      </div>
                    </div>
                    <div className="score-tracker-stats">
                      <span>Current <strong>{latest?.score ?? 0}</strong></span>
                      <span>Best <strong>{best}</strong></span>
                      <span>Resets <strong>{retries}</strong></span>
                    </div>
                    {latest?.attempts?.length ? (
                      <div className="score-tracker-attempts">
                        <strong>Previous attempts</strong>
                        <div className="score-tracker-attempt-list">
                          {latest.attempts.map((attempt) => (
                            <span key={`${latest.run_id}-${attempt.attempt_number}`}>
                              Attempt {attempt.attempt_number}: <b>{attempt.score}</b>/100
                              {attempt.best_score > attempt.score
                                ? ` · Best ${attempt.best_score}`
                                : ''}
                            </span>
                          ))}
                          <span className="score-tracker-current-attempt">
                            Current attempt: <b>{latest.score}</b>/100
                          </span>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="challenge-grid">
            {CHALLENGES.map((challenge) => (
              <ChallengeCard
                key={challenge.slug}
                number={String(challenge.order).padStart(2, '0')}
                title={challenge.name}
                category={challenge.category || ''}
                description={challenge.description || ''}
                disabled={startingChallenge || workshopTimer.expired || displaySeconds <= 0}
                onEnter={() =>
                  handleEnterChallenge(challenge)
                }
              />
            ))}
          </section>

          <div className="lobby-footer">
            <span>SESSION ACTIVE</span>
            <span>Team {session.team_name}</span>
          </div>
        </section>
      </main>
    );
  }

  if (screen === 'join') {
    return (
      <main className="app-shell">
        <section className="panel join-panel">
          <div className="eyebrow">
            SWECHA AI SECURITY LAB
          </div>

          <h1>Join the Lab</h1>

          <p className="muted">
            Enter your workshop and team credentials to access
            the security challenges.
          </p>

          <form
            className="join-form"
            onSubmit={handleJoin}
          >
            <label>
              Workshop Code

              <input
                value={workshopCode}
                onChange={(event) =>
                  setWorkshopCode(event.target.value)
                }
                placeholder="e.g. DEV-LAB"
                required
              />
            </label>

            <label>
              Team Code

              <input
                value={teamCode}
                onChange={(event) =>
                  setTeamCode(event.target.value)
                }
                placeholder="e.g. ALPHA"
                required
              />
            </label>

            <fieldset className="join-mode-options">
              <legend>Participant Session</legend>
              <label>
                <input
                  type="radio"
                  name="joinMode"
                  value="new"
                  checked={joinMode === 'new'}
                  onChange={() => setJoinMode('new')}
                />
                New Participant
              </label>
              <label>
                <input
                  type="radio"
                  name="joinMode"
                  value="resume"
                  checked={joinMode === 'resume'}
                  onChange={() => setJoinMode('resume')}
                  disabled={availableSessions.length === 0}
                />
                Resume Saved Session
              </label>
              {joinMode === 'resume' && (
                availableSessions.length > 0 ? (
                  <label>
                    Saved Session
                    <select
                      value={resumeSessionToken}
                      onChange={event => setResumeSessionToken(event.target.value)}
                      required
                    >
                      {availableSessions.map(saved => (
                        <option
                          key={saved.session_token}
                          value={saved.session_token}
                        >
                          {saved.team_name} — participant {saved.participant_id.slice(0, 8)}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <p className="muted">No saved sessions found for this workshop and team.</p>
                )
              )}
            </fieldset>

            <label>
              Display Name

              <input
                value={displayName}
                onChange={(event) =>
                  setDisplayName(event.target.value)
                }
                placeholder="Your name"
                maxLength={100}
                required
              />
            </label>

            {error && (
              <div className="error-box">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="primary-button"
              disabled={joining}
            >
              {joining
                ? 'Joining...'
                : 'Join Workshop'}
            </button>
          </form>

          <button
            type="button"
            className="text-button"
            onClick={() => {
              setError('');
              setScreen('landing');
            }}
          >
            ← Back
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div className="eyebrow">
          SWECHA AI SECURITY LAB
        </div>

        <h1>
          Break the Agent.
          <br />
          Secure the Agent.
        </h1>

        <p className="hero-copy">
          A hands-on AI security lab where you attack vulnerable
          agents, identify the weakness, apply defenses, and
          prove the fix.
        </p>

        <div className="hero-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() => setScreen('join')}
          >
            Student
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setScreen('organizer')}
          >
            Admin
          </button>
        </div>

        <div className="lab-meta">
          <div>
            <span>CHALLENGES</span>
            <strong>04</strong>
          </div>

          <div>
            <span>PHASES</span>
            <strong>03</strong>
          </div>

        </div>
      </section>
    </main>
  );
}

function ChallengeCard({
  number,
  title,
  category,
  description,
  disabled,
  onEnter,
}: {
  number: string;
  title: string;
  category: string;
  description: string;
  disabled?: boolean;
  onEnter: () => void;
}) {
  return (
    <article className="challenge-card">
      <div className="challenge-number">
        {number}
      </div>

      <div className="challenge-content">
        <div className="challenge-category">
          {category}
        </div>

        <h3>{title}</h3>

        <p>{description}</p>
      </div>

      <button
        type="button"
        className="secondary-button"
        disabled={disabled}
        onClick={onEnter}
      >
        {disabled
          ? 'Starting...'
          : 'Enter Challenge →'}
      </button>
    </article>
  );
}

export default App;
