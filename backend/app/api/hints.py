from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Challenge, ChallengeRun, LabEvent, LabSession
from app.services.score_service import apply_hint_penalty
from app.services.challenge_timer import enforce_deadline


router = APIRouter(prefix="/hints", tags=["challenge-hints"])

PENALTIES = (5, 10, 15)

HINTS = {
    "ignore-the-rules": (
        "Start with ordinary requests. Learn what information the assistant can retrieve before testing its boundaries.",
        "Compare the assistant's trusted instructions with text supplied by the user. Look for a direct attempt to override its rules.",
        "The weakness is direct prompt injection. In SECURE, consider input validation, context isolation, and output validation; then retest both the attack and legitimate requests.",
    ),
    "poisoned-doc": (
        "Explore normal knowledge-base questions and notice which documents the assistant retrieves.",
        "Retrieved documents are data, not trusted policy. Investigate whether instructions inside a document influence the assistant's response.",
        "The weakness is indirect prompt injection through retrieved content. Consider separating instructions from retrieved data and enforcing a content trust boundary; then retest.",
    ),
    "too-much-power": (
        "Map the agent's available order-management operations and identify which actions can change customer or financial state.",
        "Focus on whether a sensitive operation is authorized for the current request—not merely whether the agent has access to the tool.",
        "The weakness concerns excessive tool authority or missing per-action authorization. Consider least privilege, server-side authorization, approval gates, and parameter validation; then retest.",
    ),
    "whose-data": (
        "Learn how the current customer is identified and how a normal profile lookup works.",
        "Check whether authorization is verified for each requested customer record, rather than assuming a requested identifier is permitted.",
        "The weakness is broken object-level authorization. Consider per-record authorization, tenant isolation, and data minimization; then retest cross-customer and authorized lookups.",
    ),
}


class HintRequest(BaseModel):
    session_token: str
    run_id: UUID
    challenge_slug: str
    level: int


def _load_run(db: Session, token: str, run_id: UUID, slug: str):
    session = db.scalar(
        select(LabSession).where(
            LabSession.session_token == token,
            LabSession.status == "active",
        )
    )
    if not session:
        raise ValueError("Invalid session token")

    run = db.scalar(
        select(ChallengeRun).where(
            ChallengeRun.id == run_id,
            ChallengeRun.session_id == session.id,
        )
    )
    if not run:
        raise ValueError("Challenge run not found")

    challenge = db.scalar(
        select(Challenge).where(Challenge.id == run.challenge_id)
    )
    if not challenge or challenge.slug != slug:
        raise ValueError("Challenge slug does not match this run")

    if slug not in HINTS:
        raise ValueError("Hints are not configured for this challenge")

    return session, run


def _hint_state(run):
    runtime = dict(run.runtime_state or {})
    revealed = runtime.get("hints_revealed", [])
    if not isinstance(revealed, list):
        revealed = []
    levels = sorted({
        int(item["level"])
        for item in revealed
        if isinstance(item, dict)
        and str(item.get("level", "")).isdigit()
        and 1 <= int(item["level"]) <= 3
    })
    return runtime, levels


def _response(run, levels, slug):
    return {
        "run_id": str(run.id),
        "challenge_slug": slug,
        "score": int(run.score or 0),
        "hint_penalty": int((run.runtime_state or {}).get("hint_penalty_total", 0)),
        "hints": [
            {
                "level": level,
                "text": HINTS[slug][level - 1],
                "penalty": PENALTIES[level - 1],
            }
            for level in levels
        ],
        "next_level": max(levels, default=0) + 1 if len(levels) < 3 else None,
    }


@router.get("/status")
def hint_status(
    session_token: str,
    run_id: UUID,
    challenge_slug: str,
    db: Session = Depends(get_db),
):
    try:
        _, run = _load_run(db, session_token, run_id, challenge_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _, levels = _hint_state(run)
    result = _response(run, levels, challenge_slug)
    return result


@router.post("/reveal")
def reveal_hint(request: HintRequest, db: Session = Depends(get_db)):
    try:
        session, run = _load_run(
            db, request.session_token, request.run_id, request.challenge_slug
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        enforce_deadline(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.level not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Hint level must be 1, 2, or 3")

    runtime, levels = _hint_state(run)

    # Reopening an already revealed hint is idempotent and costs nothing.
    if request.level not in levels:
        expected = max(levels, default=0) + 1
        if request.level != expected:
            raise HTTPException(
                status_code=400,
                detail=f"Reveal hint {expected} before requesting hint {request.level}",
            )

        penalty = PENALTIES[request.level - 1]
        apply_hint_penalty(run, penalty)
        runtime = dict(run.runtime_state or {})
        revealed = list(runtime.get("hints_revealed", []))
        revealed.append({
            "level": request.level,
            "penalty": penalty,
        })
        runtime["hints_revealed"] = revealed
        runtime["hint_challenge_slug"] = request.challenge_slug
        run.runtime_state = runtime

        db.add(LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="HINT_REVEALED",
            actor="participant",
            payload={
                "challenge_slug": request.challenge_slug,
                "level": request.level,
                "penalty": penalty,
                "cumulative_penalty": runtime["hint_penalty_total"],
            },
        ))
        db.commit()
        _, levels = _hint_state(run)

    result = _response(run, levels, request.challenge_slug)
    return result
