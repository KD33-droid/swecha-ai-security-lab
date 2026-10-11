import { FormEvent, useCallback, useEffect, useState } from 'react';
import {
  getWorkshopMonitoring,
  listOrganizerWorkshops,
  organizerLogin,
} from '../../lib/api';
import type { OrganizerWorkshop } from '../../lib/api';

type JsonRecord = Record<string, any>;

type MonitoringData = {
  workshop?: JsonRecord;
  staff_role?: string;
  leaderboard?: JsonRecord[];
  participants?: JsonRecord[];
};

type Props = {
  onExit: () => void;
};

function display(value: unknown, fallback = '—'): string {
  return value === null || value === undefined || value === ''
    ? fallback
    : String(value);
}

function numberValue(value: unknown): number {
  const result = Number(value ?? 0);
  return Number.isFinite(result) ? result : 0;
}

function formatDate(value: unknown): string {
  if (!value) return 'Not recorded';
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleString();
}

function getTeamName(item: JsonRecord): string {
  return display(item.team_name ?? item.name ?? item.team?.name, 'Unnamed team');
}

function getParticipantName(item: JsonRecord): string {
  return display(item.display_name ?? item.name, 'Unnamed participant');
}

function getLatestRuns(participant: JsonRecord): JsonRecord[] {
  const runs = participant.challenges ?? participant.latest_runs ?? participant.challenge_runs ?? [];
  if (Array.isArray(runs)) return runs;

  if (runs && typeof runs === 'object') {
    return Object.entries(runs).map(([slug, run]) => ({
      ...(run as JsonRecord),
      challenge_slug: (run as JsonRecord)?.challenge_slug ?? slug,
    }));
  }

  return [];
}

export default function OrganizerDashboard({ onExit }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState('');
  const [role, setRole] = useState('');
  const [workshops, setWorkshops] = useState<OrganizerWorkshop[]>([]);
  const [workshopId, setWorkshopId] = useState('');
  const [data, setData] = useState<MonitoringData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState('');

  const loadWorkshops = useCallback(async (accessToken: string) => {
    const result = await listOrganizerWorkshops(accessToken);
    setWorkshops(result.items);
    setRole(result.staff_role);

    setWorkshopId((current) => {
      if (current && result.items.some((item) => item.id === current)) {
        return current;
      }
      return result.items[0]?.id ?? '';
    });
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await organizerLogin(username.trim(), password);
      setToken(result.access_token);
      setRole(result.role);
      setPassword('');
      await loadWorkshops(result.access_token);
    } catch (err) {
      setToken('');
      setError(err instanceof Error ? err.message : 'Login failed.');
    } finally {
      setLoading(false);
    }
  }

  const refreshMonitoring = useCallback(async (manual = false) => {
    if (!token || !workshopId) return;

    if (manual) setRefreshing(true);

    try {
      const result = await getWorkshopMonitoring<MonitoringData>(
        token,
        workshopId,
      );
      setData(result);
      setLastUpdated(new Date().toLocaleTimeString());
      setError('');
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to refresh workshop monitoring.',
      );
    } finally {
      if (manual) setRefreshing(false);
    }
  }, [token, workshopId]);

  useEffect(() => {
    if (!token || !workshopId) {
      setData(null);
      return;
    }

    void refreshMonitoring();

    const interval = window.setInterval(() => {
      void refreshMonitoring();
    }, 10_000);

    return () => window.clearInterval(interval);
  }, [token, workshopId, refreshMonitoring]);

  function logout() {
    setToken('');
    setRole('');
    setWorkshops([]);
    setWorkshopId('');
    setData(null);
    setError('');
    setLastUpdated('');
    setUsername('');
    setPassword('');
  }

  if (!token) {
    return (
      <main className="app-shell organizer-shell">
        <header className="organizer-topbar">
          <div>
            <div className="eyebrow">SWECHA AI SECURITY LAB</div>
            <h1>Staff access</h1>
            <p className="muted">Organizer and teaching assistant console</p>
          </div>
          <button className="secondary-button" onClick={onExit}>
            Back to lab
          </button>
        </header>

        <section className="panel organizer-login-panel">
          <div className="eyebrow">RESTRICTED AREA</div>
          <h2>Organizer / TA login</h2>
          <p className="muted">
            Sign in with your staff account to monitor workshops and team
            activity.
          </p>

          <form className="organizer-login-form" onSubmit={handleLogin}>
            <label htmlFor="organizer-username">Username</label>
            <input
              id="organizer-username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />

            <label htmlFor="organizer-password">Password</label>
            <input
              id="organizer-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />

            {error && <div className="error-box">{error}</div>}

            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <p className="organizer-security-note">
            Staff access is authenticated by the backend. Credentials and access
            tokens are not saved in browser storage.
          </p>
        </section>
      </main>
    );
  }

  const leaderboard = data?.leaderboard ?? [];
  const participants = data?.participants ?? [];
  const allRuns = participants.flatMap(getLatestRuns);
  const activeRuns = allRuns.filter((run) => {
    const state = String(run.state ?? run.status ?? '').toLowerCase();
    return state && !['completed', 'complete', 'failed', 'cancelled'].includes(state);
  });
  const totalHints = participants.reduce(
    (total, participant) =>
      total +
      getLatestRuns(participant).reduce(
        (sum, run) => sum + numberValue(run.hint_count),
        0,
      ),
    0,
  );
  const totalPenalty = participants.reduce(
    (total, participant) =>
      total +
      getLatestRuns(participant).reduce(
        (sum, run) => sum + numberValue(run.hint_penalty),
        0,
      ),
    0,
  );

  return (
    <main className="app-shell organizer-shell">
      <header className="organizer-topbar">
        <div>
          <div className="eyebrow">SWECHA AI SECURITY LAB / CONTROL ROOM</div>
          <h1>Workshop monitoring</h1>
          <p className="muted">
            Live team standings and participant progress
          </p>
        </div>

        <div className="organizer-toolbar">
          <span className="organizer-role">{display(role, 'STAFF').toUpperCase()}</span>
          <button
            className="secondary-button"
            onClick={() => void refreshMonitoring(true)}
            disabled={refreshing || !workshopId}
          >
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <button className="text-button" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      <section className="panel organizer-filter-panel">
        <div>
          <label htmlFor="organizer-workshop">Workshop</label>
          <select
            id="organizer-workshop"
            value={workshopId}
            onChange={(event) => setWorkshopId(event.target.value)}
          >
            {workshops.length === 0 && <option value="">No workshops available</option>}
            {workshops.map((workshop) => (
              <option key={workshop.id} value={workshop.id}>
                {workshop.name} · {workshop.status}
              </option>
            ))}
          </select>
        </div>
        <div className="organizer-update-status">
          <span className="status-dot" />
          Auto-refresh every 10 seconds
          <small>Last updated: {lastUpdated || 'Waiting for data'}</small>
        </div>
      </section>

      {error && <div className="error-box organizer-error">{error}</div>}

      {!workshopId && (
        <section className="panel organizer-empty">
          No workshops were returned for this staff account.
        </section>
      )}

      {data && (
        <>
          <section className="organizer-overview">
            <article className="panel organizer-stat">
              <span>TEAMS</span>
              <strong>{leaderboard.length}</strong>
              <small>In selected workshop</small>
            </article>
            <article className="panel organizer-stat">
              <span>PARTICIPANTS</span>
              <strong>{participants.length}</strong>
              <small>Registered participants</small>
            </article>
            <article className="panel organizer-stat">
              <span>ACTIVE RUNS</span>
              <strong>{activeRuns.length}</strong>
              <small>Non-terminal challenge runs</small>
            </article>
            <article className="panel organizer-stat">
              <span>HINTS REVEALED</span>
              <strong>{totalHints}</strong>
              <small>{totalPenalty} total score penalty</small>
            </article>
          </section>

          <section className="panel organizer-section">
            <div className="organizer-section-heading">
              <div>
                <div className="eyebrow">COMPETITION</div>
                <h2>Team leaderboard</h2>
              </div>
              <span className="muted">{leaderboard.length} teams</span>
            </div>

            {leaderboard.length === 0 ? (
              <p className="muted">No team scores are available yet.</p>
            ) : (
              <div className="organizer-table-wrap">
                <table className="organizer-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Team</th>
                      <th>Members</th>
                      <th>Total score</th>
                      <th>Challenge scores</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.map((team, index) => {
                      const challengeScores =
                        team.challenge_scores ?? team.scores_by_challenge ?? {};
                      const scoreEntries = Array.isArray(challengeScores)
                        ? challengeScores.map((item: JsonRecord) => [
                            display(item.challenge_slug ?? item.slug, 'Challenge'),
                            numberValue(item.best_score ?? item.score),
                          ] as [string, number])
                        : Object.entries(challengeScores).map(
                            ([slug, score]) => [
                              slug,
                              numberValue(
                                typeof score === 'object'
                                  ? (score as JsonRecord).score
                                  : score,
                              ),
                            ] as [string, number],
                          );

                      return (
                        <tr key={String(team.team_id ?? team.id ?? getTeamName(team))}>
                          <td><span className="organizer-rank">{team.rank ?? index + 1}</span></td>
                          <td><strong>{getTeamName(team)}</strong></td>
                          <td>{numberValue(team.participant_count ?? team.members_count)}</td>
                          <td className="organizer-score">{numberValue(team.total_score ?? team.score)}</td>
                          <td>
                            <div className="organizer-score-list">
                              {scoreEntries.length
                                ? scoreEntries.map(([slug, score]) => (
                                    <span key={slug} title={slug}>
                                      {slug}: <strong>{score}</strong>
                                    </span>
                                  ))
                                : <span className="muted">No scores</span>}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel organizer-section">
            <div className="organizer-section-heading">
              <div>
                <div className="eyebrow">LIVE ACTIVITY</div>
                <h2>Participant monitoring</h2>
              </div>
              <span className="muted">{participants.length} participants</span>
            </div>

            {participants.length === 0 ? (
              <p className="muted">No participants have joined this workshop yet.</p>
            ) : (
              <div className="organizer-table-wrap">
                <table className="organizer-table">
                  <thead>
                    <tr>
                      <th>Participant</th>
                      <th>Team</th>
                      <th>Last seen</th>
                      <th>Challenge activity</th>
                      <th>Hints / penalty</th>
                    </tr>
                  </thead>
                  <tbody>
                    {participants.map((participant, index) => {
                      const runs = getLatestRuns(participant);
                      const hints = runs.reduce(
                        (sum, run) => sum + numberValue(run.hint_count),
                        0,
                      );
                      const penalty = runs.reduce(
                        (sum, run) => sum + numberValue(run.hint_penalty),
                        0,
                      );

                      return (
                        <tr key={String(participant.participant_id ?? participant.id ?? index)}>
                          <td>
                            <strong>{getParticipantName(participant)}</strong>
                            <small className="organizer-cell-subtitle">
                              {display(participant.participant_id ?? participant.id, '')}
                            </small>
                          </td>
                          <td>{display(participant.team_name ?? participant.team?.name)}</td>
                          <td>{formatDate(participant.last_seen_at ?? participant.updated_at)}</td>
                          <td>
                            <div className="organizer-run-list">
                              {runs.length ? runs.map((run, runIndex) => (
                                <span
                                  className="organizer-run"
                                  key={String(run.run_id ?? run.id ?? run.challenge_slug ?? runIndex)}
                                >
                                  <strong>
                                    {display(run.challenge_slug ?? run.challenge_name, 'Challenge')}
                                  </strong>
                                  <small>
                                    {display(run.phase ?? run.state ?? run.status, 'Started')}
                                    {' · '}
                                    {numberValue(run.score)} pts
                                  </small>
                                </span>
                              )) : <span className="muted">No challenge runs</span>}
                            </div>
                          </td>
                          <td>
                            <strong>{hints} hints</strong>
                            <small className="organizer-cell-subtitle">
                              {penalty} penalty points
                            </small>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      <footer className="organizer-footer">
        <span>Staff monitoring · Read-only view</span>
        <button className="text-button" onClick={onExit}>Return to participant lab</button>
      </footer>
    </main>
  );
}
