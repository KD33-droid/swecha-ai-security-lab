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
    reset_count: int


class ChallengeRunResponse(BaseModel):
    run_id: UUID
    challenge_slug: str
    challenge_version: str
    phase: str
    state: str
    score: int
