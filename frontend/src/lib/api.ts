import type {
  AgentMessageResponse,
  ChallengeDefinition,
  ChallengeRun,
  ChallengeStatus,
  ChallengePhase,
  ChallengeState,
  RetestResponse,
  SecureResponse,
  Session,
  WorkshopTimer,
} from './types';

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const apiPath = `/${path.replace(/^\/+/, '')}`
    .replace(/^\/api\/v1\/?/, '');

  const response = await fetch(
    `${API_BASE_URL.replace(/\/api\/v1$/, '')}/api/v1${apiPath}`,
    {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get('content-type') || '';

  const data = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof data === 'object' &&
      data !== null &&
      'detail' in data
        ? String(data.detail)
        : `Request failed with status ${response.status}`;

    throw new Error(message);
  }

  return data as T;
}

export async function getWorkshopTimer(
  sessionToken: string,
): Promise<WorkshopTimer> {
  const query = new URLSearchParams({ session_token: sessionToken });
  return apiRequest<WorkshopTimer>(`/workshops/timer?${query.toString()}`);
}

export async function startChallenge(
  sessionToken: string,
  challengeSlug: string,
): Promise<ChallengeRun> {
  return apiRequest<ChallengeRun>(
    '/workshops/challenges/start',
    {
      method: 'POST',
      body: JSON.stringify({
        session_token: sessionToken,
        challenge_slug: challengeSlug,
      }),
    },
  );
}

export async function resetChallenge(
  sessionToken: string,
  runId: string,
): Promise<ChallengeRun> {
  return apiRequest<ChallengeRun>(
    `/workshops/challenges/${runId}/reset`,
    {
      method: 'POST',
      body: JSON.stringify({
        session_token: sessionToken,
      }),
    },
  );
}

export async function joinWorkshop(
  workshopCode: string,
  teamCode: string,
  displayName: string,
): Promise<Session> {
  return apiRequest<Session>(
    '/workshops/join',
    {
      method: 'POST',
      body: JSON.stringify({
        workshop_code: workshopCode,
        team_code: teamCode,
        display_name: displayName,
      }),
    },
  );
}

export async function listChallenges(): Promise<ChallengeDefinition[]> {
  const response = await apiRequest<{ items: ChallengeDefinition[] }>(
    '/challenges',
  );

  return response.items;
}

export async function getChallengeStatus(
  slug: string,
  sessionToken: string,
  runId: string,
): Promise<ChallengeStatus> {
  return apiRequest<ChallengeStatus>(
    `/${slug}/status?session_token=${encodeURIComponent(
      sessionToken,
    )}&run_id=${encodeURIComponent(runId)}`,
  );
}

export async function sendChallengeMessage(
  slug: string,
  sessionToken: string,
  runId: string,
  message: string,
): Promise<AgentMessageResponse> {
  return apiRequest<AgentMessageResponse>(
    `/${slug}/message`,
    {
      method: 'POST',
      body: JSON.stringify({
        session_token: sessionToken,
        run_id: runId,
        message,
      }),
    },
  );
}

export async function submitRootCause(
  slug: string,
  sessionToken: string,
  runId: string,
  rootCause: string,
): Promise<SecureResponse> {
  if (slug === 'c1') {
    return apiRequest<SecureResponse>(
      '/c1/secure/root-cause',
      {
        method: 'POST',
        body: JSON.stringify({
          session_token: sessionToken,
          run_id: runId,
          root_cause: rootCause,
        }),
      },
    );
  }

  return apiRequest<SecureResponse>(
    `/${slug}/secure`,
    {
      method: 'PATCH',
      body: JSON.stringify({
        session_token: sessionToken,
        run_id: runId,
        root_cause: rootCause,
      }),
    },
  );
}

export async function submitControls(
  slug: string,
  sessionToken: string,
  runId: string,
  controls: Record<string, Record<string, boolean>>,
): Promise<SecureResponse> {
  if (slug === 'c1') {
    return apiRequest<SecureResponse>(
      '/c1/secure/policies',
      {
        method: 'PATCH',
        body: JSON.stringify({
          session_token: sessionToken,
          run_id: runId,
          controls,
        }),
      },
    );
  }

  return apiRequest<SecureResponse>(
    `/${slug}/secure`,
    {
      method: 'PATCH',
      body: JSON.stringify({
        session_token: sessionToken,
        run_id: runId,
        controls,
      }),
    },
  );
}

export async function startRetest(
  slug: string,
  sessionToken: string,
  runId: string,
): Promise<RetestResponse> {
  const path =
    slug === 'c1'
      ? '/c1/retest/start'
      : `/${slug}/retest/start`;

  return apiRequest<RetestResponse>(path, {
    method: 'POST',
    body: JSON.stringify({
      session_token: sessionToken,
      run_id: runId,
    }),
  });
}

export async function sendRetestAttack(
  slug: string,
  sessionToken: string,
  runId: string,
  message: string,
): Promise<RetestResponse> {
  const path =
    slug === 'c1'
      ? '/c1/retest/attack'
      : `/${slug}/retest/attack`;

  return apiRequest<RetestResponse>(path, {
    method: 'POST',
    body: JSON.stringify({
      session_token: sessionToken,
      run_id: runId,
      message,
    }),
  });
}

export async function sendFunctionalityTest(
  slug: string,
  sessionToken: string,
  runId: string,
  message: string,
): Promise<RetestResponse> {
  const path =
    slug === 'c1'
      ? '/c1/retest/functionality'
      : `/${slug}/retest/functionality`;

  return apiRequest<RetestResponse>(path, {
    method: 'POST',
    body: JSON.stringify({
      session_token: sessionToken,
      run_id: runId,
      message,
    }),
  });
}



export interface HintItem {
  level: number;
  text: string;
  penalty: number;
}

export interface HintStatus {
  run_id: string;
  challenge_slug: string;
  score: number;
  hint_penalty: number;
  hints: HintItem[];
  next_level: number | null;
}

export async function getHintStatus(
  sessionToken: string,
  runId: string,
  challengeSlug: string,
): Promise<HintStatus> {
  const query = new URLSearchParams({
    session_token: sessionToken,
    run_id: runId,
    challenge_slug: challengeSlug,
  });
  return apiRequest<HintStatus>(`/hints/status?${query.toString()}`);
}

export async function revealHint(
  sessionToken: string,
  runId: string,
  challengeSlug: string,
  level: number,
): Promise<HintStatus> {
  return apiRequest<HintStatus>('/hints/reveal', {
    method: 'POST',
    body: JSON.stringify({
      session_token: sessionToken,
      run_id: runId,
      challenge_slug: challengeSlug,
      level,
    }),
  });
}

export { API_BASE_URL };


export interface OrganizerLoginResponse {
  access_token: string;
  token_type: string;
  role: "organizer" | "ta";
  expires_in: number;
}

export interface OrganizerWorkshop {
  id: string;
  name: string;
  status: string;
  leaderboard_enabled: boolean;
}

export interface OrganizerWorkshopList {
  items: OrganizerWorkshop[];
  staff_role: "organizer" | "ta";
}

export async function organizerLogin(
  username: string,
  password: string,
): Promise<OrganizerLoginResponse> {
  return apiRequest<OrganizerLoginResponse>("/organizer/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function listOrganizerWorkshops(
  token: string,
): Promise<OrganizerWorkshopList> {
  return apiRequest<OrganizerWorkshopList>("/organizer/workshops", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getWorkshopMonitoring<T = Record<string, unknown>>(
  token: string,
  workshopId: string,
): Promise<T> {
  return apiRequest<T>(
    `/organizer/workshops/${encodeURIComponent(workshopId)}/monitoring`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
}

export interface ChallengeAttemptHistoryItem {
  attempt_number: number;
  score: number;
  best_score: number;
  phase: ChallengePhase;
  state: ChallengeState;
  reset_at: string | null;
}

export interface ChallengeHistoryItem {
  run_id: string;
  challenge_slug: string;
  challenge_name: string;
  challenge_version: string;
  phase: ChallengePhase;
  state: ChallengeState;
  score: number;
  best_score: number;
  reset_count: number;
  attempts: ChallengeAttemptHistoryItem[];
  started_at: string | null;
  completed_at: string | null;
}

export interface ChallengeHistoryResponse {
  items: ChallengeHistoryItem[];
}

export async function getChallengeHistory(
  sessionToken: string,
): Promise<ChallengeHistoryResponse> {
  const query = new URLSearchParams({ session_token: sessionToken });
  return apiRequest<ChallengeHistoryResponse>(
    `/workshops/challenges/history?${query.toString()}`,
  );
}
