from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.c1 import (
    C1MessageRequest,
    C1MessageResponse,
    C1RootCauseRequest,
    C1PolicyRequest,
    C1SecureResponse,
    C1RetestStartRequest,
    C1RetestMessageRequest,
    C1RetestResponse,
)
from app.services.c1_runtime import send_c1_message
from app.services.c1_secure import set_root_cause, set_policies, secure_status
from app.services.c1_retest import start_retest, retest_attack, retest_functionality
from app.services.c1_status import get_c1_status

router = APIRouter(prefix="/c1", tags=["c1-runtime"])


@router.get("/status")
def status(session_token: str, run_id: str, db: Session = Depends(get_db)):
    try:
        from uuid import UUID
        return get_c1_status(db, session_token, UUID(run_id))
    except (ValueError, TypeError) as exc:
        bad_request(exc)


def bad_request(exc: ValueError):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/message", response_model=C1MessageResponse)
def message(request: C1MessageRequest, db: Session = Depends(get_db)):
    try:
        return send_c1_message(db, request.session_token, request.run_id, request.message)
    except ValueError as exc:
        bad_request(exc)


@router.get("/secure", response_model=C1SecureResponse)
def secure_get(session_token: str, run_id: str, db: Session = Depends(get_db)):
    try:
        from uuid import UUID
        return secure_status(db, session_token, UUID(run_id))
    except (ValueError, TypeError) as exc:
        bad_request(exc)


@router.post("/secure/root-cause")
def root_cause(request: C1RootCauseRequest, db: Session = Depends(get_db)):
    try:
        return set_root_cause(db, request.session_token, request.run_id, request.root_cause)
    except ValueError as exc:
        bad_request(exc)


@router.patch("/secure/policies", response_model=C1SecureResponse)
def policies(request: C1PolicyRequest, db: Session = Depends(get_db)):
    try:
        return set_policies(db, request.session_token, request.run_id, request.controls)
    except ValueError as exc:
        bad_request(exc)


@router.post("/retest/start", response_model=C1RetestResponse)
def retest_start(request: C1RetestStartRequest, db: Session = Depends(get_db)):
    try:
        return start_retest(db, request.session_token, request.run_id)
    except ValueError as exc:
        bad_request(exc)


@router.post("/retest/attack", response_model=C1RetestResponse)
def retest_attack_endpoint(
    request: C1RetestMessageRequest, db: Session = Depends(get_db)
):
    try:
        return retest_attack(db, request.session_token, request.run_id, request.message)
    except ValueError as exc:
        bad_request(exc)


@router.post("/retest/functionality", response_model=C1RetestResponse)
def retest_functionality_endpoint(
    request: C1RetestMessageRequest, db: Session = Depends(get_db)
):
    try:
        return retest_functionality(
            db, request.session_token, request.run_id, request.message
        )
    except ValueError as exc:
        bad_request(exc)
