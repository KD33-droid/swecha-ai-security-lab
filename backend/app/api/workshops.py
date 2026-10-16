from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.workshop import JoinRequest, JoinResponse, StartChallengeRequest, ChallengeRunResponse, ResetChallengeRequest, ResetChallengeResponse, ChallengeHistoryItem, ChallengeHistoryResponse, ChallengeAttemptHistoryItem
from app.services.workshop_service import join_workshop, start_challenge, reset_challenge_run
from app.services.challenge_timer import (
    CHALLENGE_DURATION,
    refresh_expiry,
    remaining_seconds,
    timer_status,
    utc_now,
)
from app.models import Challenge, ChallengeRun, LabSession, LabEvent
from sqlalchemy import select
from pydantic import BaseModel

router = APIRouter(prefix="/workshops", tags=["workshops"])


@router.post("/join", response_model=JoinResponse)
def join(request: JoinRequest, db: Session = Depends(get_db)):
    try:
        workshop, team, participant, session = join_workshop(
            db,
            request.workshop_code,
            request.team_code,
            request.display_name,
            request.session_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JoinResponse(session_token=session.session_token, participant_id=participant.id, team_id=team.id, workshop_id=workshop.id, team_name=team.name)


@router.post("/challenges/start", response_model=ChallengeRunResponse)
def start(request: StartChallengeRequest, db: Session = Depends(get_db)):
    try:
        run, challenge = start_challenge(db, request.session_token, request.challenge_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    timer = timer_status(run, db=db)
    return ChallengeRunResponse(
        run_id=run.id,
        challenge_slug=challenge.slug,
        challenge_version=challenge.version,
        phase=run.current_phase,
        state=run.state,
        score=run.score,
        best_score=run.best_score,
        **timer,
    )


@router.post("/challenges/{run_id}/reset", response_model=ResetChallengeResponse)
def reset(run_id, request: ResetChallengeRequest, db: Session = Depends(get_db)):
    try:
        run = reset_challenge_run(db, request.session_token, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    timer = timer_status(run, db=db)
    return ResetChallengeResponse(
        run_id=run.id,
        phase=run.current_phase,
        state=run.state,
        score=run.score,
        best_score=run.best_score,
        reset_count=run.reset_count,
        **timer,
    )



@router.get("/timer")
def workshop_timer(session_token: str, db: Session = Depends(get_db)):
    """Return the session-wide timer; querying it never starts the timer."""
    session = db.scalar(
        select(LabSession).where(
            LabSession.session_token == session_token,
            LabSession.status == "active",
        )
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session token")

    duration_seconds = int(CHALLENGE_DURATION.total_seconds())
    deadline = session.deadline_at
    seconds = remaining_seconds(deadline) if deadline is not None else duration_seconds
    expired = deadline is not None and seconds == 0

    if expired:
        active_runs = db.scalars(
            select(ChallengeRun).where(
                ChallengeRun.session_id == session.id,
                ChallengeRun.state == "active",
            )
        ).all()
        for run in active_runs:
            refresh_expiry(db, run)

    return {
        "started": session.started_at is not None,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "deadline_at": deadline.isoformat() if deadline else None,
        "remaining_seconds": seconds,
        "timer_warning": session.started_at is not None and 0 < seconds <= 600,
        "expired": expired,
    }


class ChallengeHistoryRequest(BaseModel):
    session_token: str


@router.get("/challenges/history", response_model=ChallengeHistoryResponse)
def challenge_history(session_token: str, db: Session = Depends(get_db)):
    session = db.scalar(
        select(LabSession).where(
            LabSession.session_token == session_token,
            LabSession.status == "active",
        )
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session token")

    rows = db.execute(
        select(ChallengeRun, Challenge)
        .join(Challenge, Challenge.id == ChallengeRun.challenge_id)
        .where(ChallengeRun.session_id == session.id)
        .order_by(ChallengeRun.started_at.desc())
    ).all()

    run_ids = [run.id for run, _ in rows]
    events_by_run = {run_id: [] for run_id in run_ids}

    if run_ids:
        events = db.scalars(
            select(LabEvent)
            .where(
                LabEvent.session_id == session.id,
                LabEvent.challenge_run_id.in_(run_ids),
                LabEvent.event_type == "CHALLENGE_RESET",
            )
            .order_by(LabEvent.timestamp.asc())
        ).all()

        for event in events:
            payload = event.payload or {}
            events_by_run[event.challenge_run_id].append(
                ChallengeAttemptHistoryItem(
                    attempt_number=int(payload.get("attempt_number", payload.get("reset_count", 1))),
                    score=int(payload.get("attempt_score", 0)),
                    best_score=int(payload.get("best_score", payload.get("attempt_score", 0))),
                    phase=str(payload.get("phase", "break")),
                    state=str(payload.get("state", "active")),
                    reset_at=event.timestamp.isoformat() if event.timestamp else None,
                )
            )

    items = [
        ChallengeHistoryItem(
            run_id=run.id,
            challenge_slug=challenge.slug,
            challenge_name=challenge.name,
            challenge_version=run.challenge_version,
            phase=run.current_phase,
            state=run.state,
            score=run.score,
            best_score=max(int(run.best_score or 0), int(run.score or 0)),
            reset_count=run.reset_count or 0,
            attempts=events_by_run[run.id],
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
        )
        for run, challenge in rows
    ]
    return ChallengeHistoryResponse(items=items)
