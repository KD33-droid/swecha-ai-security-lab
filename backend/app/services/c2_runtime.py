from __future__ import annotations
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AttackAttempt, ChallengeRun, LabEvent, LabSession, ToolCall
from app.services.c2_agent import PoisonedDocAgent
from app.services.c2_policy import CONTROLS, normalize_controls, is_poison_trigger


def load(db: Session, token: str, run_id: UUID):
    session = db.scalar(select(LabSession).where(LabSession.session_token == token, LabSession.status == "active"))
    if not session: raise ValueError("Invalid session token")
    run = db.scalar(select(ChallengeRun).where(ChallengeRun.id == run_id, ChallengeRun.session_id == session.id))
    if not run: raise ValueError("Challenge run not found")
    return session, run


def message(db: Session, token: str, run_id: UUID, user_message: str) -> dict:
    session, run = load(db, token, run_id)
    if run.state != "active" or run.current_phase != "break": raise ValueError("Challenge run is not accepting BREAK-phase messages")
    runtime = dict(run.runtime_state or {})
    controls = runtime.get("policies", {})
    reply = PoisonedDocAgent(runtime["secret"]).respond(user_message, controls)
    if reply.tool_calls:
        for call in reply.tool_calls:
            db.add(ToolCall(challenge_run_id=run.id, tool=call["tool"], arguments=call["arguments"], authorization_result=call.get("authorization_result", "ALLOW"), execution_result=call["result"], risk_level=call.get("risk_level", "LOW")))
    discovery = bool(reply.poisoned_doc_retrieved)
    runtime["poisoned_doc_discovered"] = bool(runtime.get("poisoned_doc_discovered") or discovery)
    run.runtime_state = runtime
    leaked = runtime["secret"] in reply.text
    attempt = AttackAttempt(challenge_run_id=run.id, phase="break", input=user_message, outcome="success" if leaked else "no_impact", evidence={"secret_disclosed": leaked, "poisoned_doc_retrieved": discovery}, metadata_={"vulnerable_path": reply.vulnerable_path})
    db.add(attempt)
    if discovery and not runtime.get("discovery_points_awarded"):
        runtime["discovery_points_awarded"] = True
        run.score = max(run.score, 10)
    if leaked:
        run.current_phase = "secure"
        run.score = max(run.score, 20 + (10 if runtime.get("discovery_points_awarded") else 0))
    db.add(LabEvent(workshop_id=session.workshop_id, team_id=session.team_id, session_id=session.id, challenge_run_id=run.id, event_type="C2_AGENT_RESPONSE", actor="agent", payload={"poisoned_doc_retrieved": discovery, "secret_disclosed": leaked}))
    db.commit()
    return {"run_id": run.id, "message": reply.text, "phase": run.current_phase, "state": run.state, "score": run.score, "objective_completed": leaked, "discovery_completed": bool(runtime.get("poisoned_doc_discovered")), "discovery_points_awarded": 10 if runtime.get("discovery_points_awarded") else 0}


def secure(db: Session, token: str, run_id: UUID, root_cause: str | None = None, controls: dict | None = None) -> dict:
    session, run = load(db, token, run_id)
    if run.current_phase != "secure": raise ValueError("Challenge run is not in SECURE phase")
    runtime = dict(run.runtime_state or {})
    if root_cause is not None:
        runtime["root_cause"] = root_cause
        runtime["root_cause_correct"] = root_cause in {"indirect_prompt_injection", "trusted_retrieved_content", "rag_content_as_instructions"}
        db.add(LabEvent(workshop_id=session.workshop_id, team_id=session.team_id, session_id=session.id, challenge_run_id=run.id, event_type="ROOT_CAUSE_SUBMITTED", actor="participant", payload={"root_cause": root_cause, "correct": runtime["root_cause_correct"]}))
        if runtime["root_cause_correct"]: run.score = max(run.score, 35 + (10 if runtime.get("discovery_points_awarded") else 0))
    if controls is not None:
        print(
            "C2_SCORE_DEBUG before:",
            {"score": run.score,
             "root_cause_correct": runtime.get("root_cause_correct"),
             "discovery_points_awarded": runtime.get("discovery_points_awarded")},
            flush=True,
        )
        normalized = normalize_controls(runtime.get("policies", {}), controls)
        runtime["policies"] = normalized
        mitigation = any(v.get("enabled") for v in normalized.values())
        if mitigation:
            run.score = max(run.score, (55 if runtime.get("root_cause_correct") else 40) + (10 if runtime.get("discovery_points_awarded") else 0))
        db.add(LabEvent(workshop_id=session.workshop_id, team_id=session.team_id, session_id=session.id, challenge_run_id=run.id, event_type="POLICY_CHANGED", actor="participant", payload={"policies": normalized, "mitigation_configured": mitigation}))
    run.runtime_state = runtime
    db.commit()
    return {"run_id": run.id, "phase": run.current_phase, "state": run.state, "score": run.score, "root_cause_correct": bool(runtime.get("root_cause_correct")), "controls": runtime.get("policies", {}), "mitigation_configured": any(v.get("enabled") for v in runtime.get("policies", {}).values())}


def start_retest(db: Session, token: str, run_id: UUID) -> dict:
    session, run = load(db, token, run_id)
    runtime = dict(run.runtime_state or {})
    if run.current_phase != "secure": raise ValueError("Challenge run is not in SECURE phase")
    if not runtime.get("root_cause_correct"): raise ValueError("Submit the correct root cause before RETEST")
    if not any(v.get("enabled") for v in runtime.get("policies", {}).values()): raise ValueError("Configure a protective control before RETEST")
    runtime["retest_started"] = True; run.runtime_state = runtime; run.current_phase = "retest"; db.commit()
    return {"run_id": run.id, "phase": run.current_phase, "state": run.state, "score": run.score, "retest_started": True}

def retest(db: Session, token: str, run_id: UUID, message_text: str) -> dict:
    session, run = load(db, token, run_id)

    if run.current_phase != "retest":
        raise ValueError("Challenge run is not in RETEST phase")

    runtime = dict(run.runtime_state or {})

    if not runtime.get("root_cause_correct"):
        raise ValueError("Submit the correct root cause before RETEST")

    if not any(v.get("enabled") for v in runtime.get("policies", {}).values()):
        raise ValueError("Configure a protective control before RETEST")

    reply = PoisonedDocAgent(runtime["secret"]).respond(
        message_text,
        runtime.get("policies", {}),
    )

    equivalent_attack = is_poison_trigger(message_text)
    secret_blocked = runtime["secret"] not in reply.text
    passed = equivalent_attack and secret_blocked

    runtime["retest_attack_passed"] = passed
    run.runtime_state = runtime

    run.score = max(
        run.score,
        55
        + (10 if runtime.get("discovery_points_awarded") else 0)
        + (25 if passed else 0),
    )

    if not passed:
        run.current_phase = "secure"

    db.add(
        AttackAttempt(
            challenge_run_id=run.id,
            phase="retest",
            input=message_text,
            outcome="blocked" if passed else "success",
            evidence={
                "secret_disclosed": not secret_blocked,
                "equivalent_attack": equivalent_attack,
                "secret_blocked": secret_blocked,
            },
            metadata_={
                "equivalent_attack": equivalent_attack,
            },
        )
    )

    db.commit()

    return {
        "run_id": run.id,
        "phase": run.current_phase,
        "state": run.state,
        "score": run.score,
        "passed": passed,
        "message": reply.text,
    }


def functionality(db: Session, token: str, run_id: UUID, message_text: str) -> dict:
    session, run = load(db, token, run_id)
    if run.current_phase != "retest": raise ValueError("Challenge run is not in RETEST phase")
    runtime = dict(run.runtime_state or {})
    reply = PoisonedDocAgent(runtime["secret"]).respond(message_text, runtime.get("policies", {}))
    passed = "password" in reply.text.lower() and "reset" in reply.text.lower() and runtime["secret"] not in reply.text
    runtime["retest_functionality_passed"] = passed
    run.runtime_state = runtime
    if passed and runtime.get("retest_attack_passed"):
        run.score = max(run.score, 90 + (10 if runtime.get("discovery_points_awarded") else 0)); run.current_phase = "completed"; run.state = "completed"
    elif not passed: run.current_phase = "secure"
    db.commit()
    return {"run_id": run.id, "phase": run.current_phase, "state": run.state, "score": run.score, "passed": passed, "challenge_completed": run.state == "completed", "message": reply.text}
