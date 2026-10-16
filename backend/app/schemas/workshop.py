from uuid import UUID
from pydantic import BaseModel, Field


class JoinRequest(BaseModel):
    workshop_code: str = Field(min_length=2, max_length=32)
    team_code: str = Field(min_length=2, max_length=32)
    display_name: str = Field(min_length=1, max_length=100)
    session_token: str | None = Field(default=None, min_length=20, max_length=100)


class JoinResponse(BaseModel):
    session_token: str
    participant_id: UUID
    team_id: UUID
    workshop_id: UUID
    team_name: str


class StartChallengeRequest(BaseModel):
    session_token: str
    challenge_slug: str


class ResetChallengeRequest(BaseModel):
    session_token: str


class ResetChallengeResponse(BaseModel):
    run_id: UUID
    phase: str
    state: str
    score: int
    best_score: int = 0
    reset_count: int
    deadline_at: str | None = None
    remaining_seconds: int | None = None
    timer_warning: bool = False


class ChallengeRunResponse(BaseModel):
    run_id: UUID
    challenge_slug: str
    challenge_version: str
    phase: str
    state: str
    score: int
    best_score: int = 0
    deadline_at: str | None = None
    remaining_seconds: int | None = None
    timer_warning: bool = False


class ChallengeAttemptHistoryItem(BaseModel):
    attempt_number: int
    score: int
    best_score: int
    phase: str
    state: str
    reset_at: str | None = None


class ChallengeHistoryItem(BaseModel):
    run_id: UUID
    challenge_slug: str
    challenge_name: str
    challenge_version: str
    phase: str
    state: str
    score: int
    best_score: int = 0
    reset_count: int = 0
    attempts: list[ChallengeAttemptHistoryItem] = []
    started_at: str | None = None
    completed_at: str | None = None


class ChallengeHistoryResponse(BaseModel):
    items: list[ChallengeHistoryItem]
