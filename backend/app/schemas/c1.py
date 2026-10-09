from uuid import UUID
from pydantic import BaseModel, Field


class C1MessageRequest(BaseModel):
    session_token: str = Field(min_length=20, max_length=100)
    run_id: UUID
    message: str = Field(min_length=1, max_length=4000)


class C1MessageResponse(BaseModel):
    run_id: UUID
    message: str
    phase: str
    state: str
    score: int
    objective_completed: bool
    discovery_completed: bool = False
    discovery_documents_found: int = 0
    discovery_points_awarded: int = 0


class C1RootCauseRequest(BaseModel):
    session_token: str = Field(min_length=20, max_length=100)
    run_id: UUID
    root_cause: str = Field(min_length=1, max_length=100)


class C1PolicyRequest(BaseModel):
    session_token: str = Field(min_length=20, max_length=100)
    run_id: UUID
    controls: dict[str, dict[str, bool]]


class C1SecureResponse(BaseModel):
    run_id: UUID
    phase: str
    state: str
    score: int
    root_cause_correct: bool
    controls: dict[str, dict[str, bool]]
    mitigation_configured: bool


class C1RetestStartRequest(BaseModel):
    session_token: str = Field(min_length=20, max_length=100)
    run_id: UUID


class C1RetestMessageRequest(BaseModel):
    session_token: str = Field(min_length=20, max_length=100)
    run_id: UUID
    message: str = Field(min_length=1, max_length=4000)


class C1RetestResponse(BaseModel):
    run_id: UUID
    phase: str
    state: str
    score: int
    impact_result: bool | None = None
    functionality_result: bool | None = None
    retest_passed: bool
    challenge_completed: bool
