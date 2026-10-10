import type {
  AgentMessageResponse,
  ChallengeDefinition,
  ChallengeRun,
  ChallengeStatus,
  RetestResponse,
  SecureResponse,
  Session,
} from './types';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const apiPath = path.startsWith('/api/v1/')
    ? path
    : `/api/v1${path}`;

  const response = await fetch(`${API_BASE_URL}${apiPath}`, {
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

export { API_BASE_URL };
