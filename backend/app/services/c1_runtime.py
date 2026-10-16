from __future__ import annotations

from app.services.score_service import apply_score_floor
from app.services.challenge_timer import enforce_deadline

import re
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.runtime import LocalNexaAssist
from app.models import AttackAttempt, ChallengeRun, LabEvent, LabSession, Participant
from app.tools.knowledge import KnowledgeBase

SECRET_RE = re.compile(r"NEXA-C1-[A-F0-9]{4}")
DISCOVERY_DOCUMENTS = {"KB-001", "KB-002", "KB-003"}


def _apply_discovery(run: ChallengeRun, reply) -> bool:
    """Award C1 discovery once the learner has explored two normal support documents."""
    runtime = dict(run.runtime_state or {})
    discovered = set(runtime.get("discovery_documents", []))
    for call in reply.tool_calls:
        if call.get("tool") == "knowledge_read":
            document_id = call.get("arguments", {}).get("document_id")
            if document_id in DISCOVERY_DOCUMENTS:
                discovered.add(document_id)
    runtime["discovery_documents"] = sorted(discovered)
    completed = bool(runtime.get("discovery_completed"))
    if len(discovered) >= 2 and not completed:
        runtime["discovery_completed"] = True
        completed = True
    run.runtime_state = runtime
    return completed and not bool((run.runtime_state or {}).get("discovery_points_awarded"))


def _score_discovery_award(run: ChallengeRun) -> bool:
    runtime = dict(run.runtime_state or {})
    if not runtime.get("discovery_completed") or runtime.get("discovery_points_awarded"):
        return False
    runtime["discovery_points_awarded"] = True
    run.runtime_state = runtime
    apply_score_floor(run, 10)
    return True


def _load_run_for_session(db: Session, session_token: str, run_id: UUID):
    session = db.scalar(select(LabSession).where(LabSession.session_token == session_token, LabSession.status == "active"))
    if not session:
        raise ValueError("Invalid session token")
    run = db.scalar(select(ChallengeRun).where(ChallengeRun.id == run_id, ChallengeRun.session_id == session.id))
    if not run:
        raise ValueError("Challenge run not found")
    return session, run


def send_c1_message(db: Session, session_token: str, run_id: UUID, message: str) -> dict:
    session, run = _load_run_for_session(db, session_token, run_id)
    enforce_deadline(db, run)
    if run.state != "active" or run.current_phase != "break":
        raise ValueError("Challenge run is not accepting BREAK-phase messages")

    secret = run.runtime_state.get("secret")
    kb = KnowledgeBase(secret)
    policies = run.runtime_state.get("policies", {})
    agent = LocalNexaAssist(kb, secret)
    history = run.runtime_state.get("conversation", [])
    reply = agent.respond(message, history, policies)

    discovery_ready = _apply_discovery(run, reply)
    discovery_awarded = _score_discovery_award(run) if discovery_ready else False

    history.extend([
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply.text},
    ])
    run.runtime_state = {**run.runtime_state, "conversation": history[-20:]}

    for call in reply.tool_calls:
        db.add(
            __import__("app.models", fromlist=["ToolCall"]).ToolCall(
                challenge_run_id=run.id,
                tool=call["tool"],
                arguments=call["arguments"],
                authorization_result="ALLOW",
                execution_result=call["result"],
                risk_level="LOW",
            )
        )
        db.add(
            LabEvent(
                workshop_id=session.workshop_id,
                team_id=session.team_id,
                session_id=session.id,
                challenge_run_id=run.id,
                event_type="TOOL_ALLOWED",
                actor="agent",
                payload={"tool": call["tool"], "arguments": call["arguments"]},
            )
        )

    if discovery_awarded:
        db.add(
            LabEvent(
                workshop_id=session.workshop_id,
                team_id=session.team_id,
                session_id=session.id,
                challenge_run_id=run.id,
                event_type="DISCOVERY_COMPLETED",
                actor="system",
                payload={"objective": "agent_behavior_discovery", "points": 10},
            )
        )

    disclosure = bool(secret and secret in reply.text)
    attempt = AttackAttempt(
        challenge_run_id=run.id,
        phase="break",
        input=message,
        outcome="success" if disclosure else "no_impact",
        evidence={"secret_disclosed": disclosure},
        metadata_={"vulnerable_path": reply.vulnerable_path},
    )
    db.add(attempt)
    db.flush()

    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="AGENT_RESPONSE",
            actor="agent",
            payload={"secret_disclosed": disclosure},
        )
    )

    if disclosure:
        run.current_phase = "secure"
        runtime = dict(run.runtime_state or {})
        runtime["protected_secret_disclosed"] = True
        run.runtime_state = runtime
        apply_score_floor(run, 20 + (10 if (run.runtime_state or {}).get("discovery_completed") else 0))
        db.add(
            LabEvent(
                workshop_id=session.workshop_id,
                team_id=session.team_id,
                session_id=session.id,
                challenge_run_id=run.id,
                event_type="OBJECTIVE_COMPLETED",
                actor="system",
                payload={"objective": "protected_secret_disclosure", "points": 20, "attack_attempt_id": str(attempt.id)},
            )
        )

    db.commit()
    runtime = run.runtime_state or {}
    discovered = runtime.get("discovery_documents", [])
    return {
        "run_id": run.id,
        "message": reply.text,
        "phase": run.current_phase,
        "state": run.state,
        "score": run.score,
        "objective_completed": disclosure,
        "discovery_completed": bool(runtime.get("discovery_completed")),
        "discovery_documents_found": len(discovered),
        "discovery_points_awarded": 10 if runtime.get("discovery_points_awarded") else 0,
    }
