from __future__ import annotations

from app.services.score_service import apply_score_floor
from app.services.challenge_timer import enforce_deadline

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChallengeRun, LabEvent, LabSession, PolicyChange
from app.services.policy_engine import (
    CORRECT_ROOT_CAUSES,
    normalize_policies,
    any_protective_control_enabled,
)


def load_secure_run(db: Session, session_token: str, run_id: UUID):
    session = db.scalar(
        select(LabSession).where(
            LabSession.session_token == session_token,
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

    if run.current_phase != "secure":
        raise ValueError("Challenge run is not in SECURE phase")

    return session, run


def _sync_secure_score(run: ChallengeRun) -> None:
    """
    Calculate the C1 SECURE-phase score from the current
    server-authoritative challenge state.

    Discovery       = 10
    Exploitation    = 20
    Root cause      = 15
    Mitigation      = 20

    Maximum SECURE-phase score = 65.

    The calculation is intentionally order-independent.
    """

    runtime = run.runtime_state or {}

    score = 0

    if runtime.get("discovery_completed"):
        score += 10

    if runtime.get("protected_secret_disclosed"):
        score += 20

    if runtime.get("root_cause_correct"):
        score += 15

    if any_protective_control_enabled(runtime.get("policies", {})):
        score += 20

    apply_score_floor(run, score)


def set_root_cause(
    db: Session,
    session_token: str,
    run_id: UUID,
    root_cause: str,
) -> dict:
    session, run = load_secure_run(db, session_token, run_id)
    enforce_deadline(db, run)

    correct = root_cause in CORRECT_ROOT_CAUSES

    runtime = dict(run.runtime_state or {})
    runtime["root_cause"] = root_cause
    runtime["root_cause_correct"] = correct
    run.runtime_state = runtime

    # Recalculate the complete SECURE score so that
    # root cause and mitigation can be submitted in either order.
    _sync_secure_score(run)

    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="ROOT_CAUSE_SUBMITTED",
            actor="participant",
            payload={
                "root_cause": root_cause,
                "correct": correct,
            },
        )
    )

    db.commit()

    return {
        "run_id": run.id,
        "root_cause_correct": correct,
        "score": run.score,
        "phase": run.current_phase,
    }


def set_policies(
    db: Session,
    session_token: str,
    run_id: UUID,
    requested: dict,
) -> dict:
    session, run = load_secure_run(db, session_token, run_id)
    enforce_deadline(db, run)

    current = dict((run.runtime_state or {}).get("policies", {}))
    normalized = normalize_policies(current, requested)
    changed_by = session.participant_id

    for name in normalized:
        old = current.get(name, {"enabled": False})
        new = normalized[name]

        if old != new:
            db.add(
                PolicyChange(
                    challenge_run_id=run.id,
                    policy=name,
                    old_configuration=old,
                    new_configuration=new,
                    changed_by=changed_by,
                )
            )

    runtime = dict(run.runtime_state or {})
    runtime["policies"] = normalized
    run.runtime_state = runtime

    mitigation = any_protective_control_enabled(normalized)

    # Recalculate the complete SECURE score.
    _sync_secure_score(run)

    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="POLICY_CHANGED",
            actor="participant",
            payload={
                "policies": normalized,
                "mitigation_configured": mitigation,
            },
        )
    )

    db.commit()

    return {
        "run_id": run.id,
        "phase": run.current_phase,
        "state": run.state,
        "score": run.score,
        "root_cause_correct": bool(
            runtime.get("root_cause_correct", False)
        ),
        "controls": normalized,
        "mitigation_configured": mitigation,
    }


def secure_status(
    db: Session,
    session_token: str,
    run_id: UUID,
) -> dict:
    session, run = load_secure_run(db, session_token, run_id)

    runtime = run.runtime_state or {}
    controls = runtime.get("policies", {})

    return {
        "run_id": run.id,
        "phase": run.current_phase,
        "state": run.state,
        "score": run.score,
        "root_cause_correct": bool(
            runtime.get("root_cause_correct", False)
        ),
        "controls": controls,
        "mitigation_configured": any_protective_control_enabled(
            controls
        ),
    }
