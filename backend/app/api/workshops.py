from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.workshop import JoinRequest, JoinResponse, StartChallengeRequest, ChallengeRunResponse, ResetChallengeRequest, ResetChallengeResponse
from app.services.workshop_service import join_workshop, start_challenge, reset_challenge_run

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
    return ChallengeRunResponse(run_id=run.id, challenge_slug=challenge.slug, challenge_version=challenge.version, phase=run.current_phase, state=run.state, score=run.score)


@router.post("/challenges/{run_id}/reset", response_model=ResetChallengeResponse)
def reset(run_id, request: ResetChallengeRequest, db: Session = Depends(get_db)):
    try:
        run = reset_challenge_run(db, request.session_token, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResetChallengeResponse(
        run_id=run.id, phase=run.current_phase, state=run.state,
        score=run.score, reset_count=run.reset_count,
    )
