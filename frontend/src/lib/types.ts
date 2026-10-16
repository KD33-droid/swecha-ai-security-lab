export type ChallengePhase = 'break' | 'secure' | 'retest' | 'expired';
export type ChallengeState = 'locked' | 'active' | 'completed' | 'expired';

export interface ChallengeDefinition {
  slug: string;
  name: string;
  description?: string;
  category?: string;
  difficulty?: string;
  order?: number;
}

export interface WorkshopTimer {
  started: boolean;
  started_at: string | null;
  deadline_at: string | null;
  remaining_seconds: number;
  timer_warning: boolean;
  expired: boolean;
}

export interface ChallengeRun {
  run_id: string;
  challenge_slug: string;
  challenge_version?: string;
  phase: ChallengePhase;
  state: ChallengeState;
  score: number;
  deadline_at?: string | null;
  remaining_seconds?: number | null;
  timer_warning?: boolean;
}

export interface Session {
  session_token: string;
  participant_id: string;
  team_id: string;
  workshop_id: string;
  team_name: string;
}

export interface ChallengeStatus {
  run_id: string;
  phase: ChallengePhase;
  state: ChallengeState;
  score: number;
  best_score?: number;
  deadline_at?: string | null;
  remaining_seconds?: number | null;
  timer_warning?: boolean;

  discovery_completed?: boolean;
  discovery_points_awarded?: number;

  objective_completed?: boolean;

  root_cause_correct?: boolean;
  controls?: Record<string, Record<string, boolean>>;
  mitigation_configured?: boolean;

  retest_started?: boolean;
  retest_attack_passed?: boolean | null;
  retest_functionality_passed?: boolean | null;
}

export interface AgentMessageResponse {
  run_id: string;
  message: string;
  phase: ChallengePhase;
  state: ChallengeState;
  score: number;
  objective_completed?: boolean;
  discovery_completed?: boolean;
  discovery_documents_found?: number;
  discovery_points_awarded?: number;
}

export interface SecureResponse {
  run_id: string;
  phase: ChallengePhase;
  state: ChallengeState;
  score: number;
  root_cause_correct: boolean;
  controls: Record<string, Record<string, boolean>>;
  mitigation_configured: boolean;
}

export interface RetestResponse {
  run_id: string;
  phase: ChallengePhase;
  state: ChallengeState;
  score: number;
  passed?: boolean;
  retest_passed?: boolean;
  challenge_completed?: boolean;
  impact_result?: boolean | null;
  functionality_result?: boolean | null;
  message?: string;
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

export interface ApiError {
  detail: string;
}
