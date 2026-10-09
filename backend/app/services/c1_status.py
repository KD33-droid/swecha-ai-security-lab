from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChallengeRun, LabSession
from app.services.policy_engine import any_protective_control_enabled


def get_c1_status(db: Session, session_token: str, run_id: UUID) -> dict:
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

    runtime = run.runtime_state or {}
    controls = runtime.get("policies", {})
    discovered = runtime.get("discovery_documents", [])
    discovery_completed = bool(runtime.get("discovery_completed"))

    return {
        "run_id": run.id,
        "phase": run.current_phase,
        "state": run.state,
        "score": run.score,
        "discovery": {
            "documents_found": len(discovered),
            "document_ids": discovered,
            "completed": discovery_completed,
            "points_awarded": 10 if runtime.get("discovery_points_awarded") else 0,
        },
        "root_cause_correct": bool(runtime.get("root_cause_correct", False)),
        "controls": controls,
        "mitigation_configured": any_protective_control_enabled(controls),
        "retest": {
            "started": bool(runtime.get("retest_started", False)),
            "impact_result": runtime.get("retest_impact_result"),
            "functionality_result": runtime.get("retest_functionality_result"),
        },
    }
