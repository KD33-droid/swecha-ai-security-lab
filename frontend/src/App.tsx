import { FormEvent, useState, useEffect } from 'react';
import {
  apiRequest,
  startChallenge,
} from './lib/api';
import type {
  ChallengeDefinition,
  ChallengeRun,
  Session,
} from './lib/types';
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

  const [joining, setJoining] = useState(false);
  const [startingChallenge, setStartingChallenge] = useState(false);
  const [error, setError] = useState('');

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
      saved[registryKey] = session;
      localStorage.setItem('swecha_sessions', JSON.stringify(saved));
    } catch {
      console.error('Could not update saved team sessions.');
    }
  }, [session]);

  async function handleJoin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setJoining(true);

    const normalizedWorkshop = workshopCode.trim().toUpperCase();
    const normalizedTeam = teamCode.trim().toUpperCase();
    const joinKey = `${normalizedWorkshop}::${normalizedTeam}`;

    function codeFromTeamName(name: string): string {
      const normalized = name.trim().toUpperCase();
      const known: Record<string, string> = {
        'TEAM ALPHA': 'ALPHA',
        'TEAM BETA': 'BETA',
        'TEAM GAMMA': 'GAMMA',
        'REJOIN TEST': 'REJOIN',
      };

      return known[normalized] ??
        normalized.replace(/^TEAM\s+/, '').replace(/\s+/g, '_');
    }

    let registry: Record<string, Session> = {};
    try {
      registry = JSON.parse(
        localStorage.getItem('swecha_sessions') || '{}'
      );
    } catch {
      registry = {};
    }

    // Preserve the currently active team's session before switching.
    if (session) {
      const currentTeamCode = codeFromTeamName(session.team_name);
      const currentKey = `${normalizedWorkshop}::${currentTeamCode}`;
      registry[currentKey] = session;
    }

    // Persist all known sessions before making the request.
    localStorage.setItem('swecha_sessions', JSON.stringify(registry));

    // Reuse the token belonging to the requested team, never another team.
    const matchingSavedSession = registry[joinKey];
    const activeSessionMatches =
      session &&
      codeFromTeamName(session.team_name) === normalizedTeam;

    const token =
      matchingSavedSession?.session_token ??
      (activeSessionMatches ? session.session_token : null);

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

      registry[joinKey] = result;
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
    if (!session || startingChallenge) {
      return;
    }

    setError('');
    setStartingChallenge(true);

    try {
      const run = await startChallenge(
        session.session_token,
        challenge.slug,
      );      localStorage.setItem(
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
        onExit={() => setScreen(session ? 'lobby' : 'landing')}
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

          <section className="challenge-grid">
            {CHALLENGES.map((challenge) => (
              <ChallengeCard
                key={challenge.slug}
                number={String(challenge.order).padStart(2, '0')}
                title={challenge.name}
                category={challenge.category || ''}
                description={challenge.description || ''}
                disabled={startingChallenge}
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
