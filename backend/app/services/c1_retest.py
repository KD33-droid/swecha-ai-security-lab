from __future__ import annotations

from app.services.score_service import apply_score_floor
from app.services.challenge_timer import enforce_deadline

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.runtime import LocalNexaAssist
from app.models import AttackAttempt, ChallengeRun, LabEvent, LabSession, Retest, ToolCall
from app.services.policy_engine import any_protective_control_enabled, is_c1_prompt_injection
from app.tools.knowledge import KnowledgeBase



def _load_retest_run(db: Session, session_token: str, run_id: UUID):
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
    return session, run


def _active_retest(db: Session, run_id: UUID) -> Retest | None:
    return db.scalar(
        select(Retest)
        .where(Retest.challenge_run_id == run_id)
        .order_by(Retest.started_at.desc())
    )


def _response(
    run: ChallengeRun,
    retest: Retest,
    *,
    challenge_completed: bool = False,
) -> dict:
    return {
        "run_id": run.id,
        "phase": run.current_phase,
        "state": run.state,
        "score": run.score,
        "impact_result": retest.impact_result,
        "functionality_result": retest.functionality_result,
        "retest_passed": bool(
            retest.impact_result is True and retest.functionality_result is True
        ),
        "challenge_completed": challenge_completed,
    }


def start_retest(db: Session, session_token: str, run_id: UUID) -> dict:
    session, run = _load_retest_run(db, session_token, run_id)
    enforce_deadline(db, run)

    if run.state != "active":
        raise ValueError("Challenge run is not active")
    if run.current_phase != "secure":
        raise ValueError("Challenge run is not in SECURE phase")

    runtime = dict(run.runtime_state or {})
    if not runtime.get("root_cause_correct"):
        raise ValueError("Submit the correct root cause before starting RETEST")

    policies = runtime.get("policies", {})
    if not any_protective_control_enabled(policies):
        raise ValueError("Configure at least one protective control before RETEST")

    existing = _active_retest(db, run.id)
    if existing and existing.result is None:
        run.current_phase = "retest"
        db.commit()
        return _response(run, existing)

    retest = Retest(
        challenge_run_id=run.id,
        result=None,
        impact_result=None,
        functionality_result=None,
        score=0,
    )
    db.add(retest)
    db.flush()

    run.current_phase = "retest"
    runtime["active_retest_id"] = str(retest.id)
    run.runtime_state = runtime

    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="RETEST_STARTED",
            actor="participant",
            payload={"retest_id": str(retest.id)},
        )
    )
    db.commit()
    return _response(run, retest)


def _ensure_retest(db: Session, session_token: str, run_id: UUID):
    session, run = _load_retest_run(db, session_token, run_id)
    enforce_deadline(db, run)
    if run.state != "active" or run.current_phase != "retest":
        raise ValueError("Challenge run is not in RETEST phase")

    retest = _active_retest(db, run.id)
    if not retest:
        raise ValueError("Retest has not been started")
    return session, run, retest


def _record_tool_calls(db: Session, session, run, reply):
    for call in reply.tool_calls:
        db.add(
            ToolCall(
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


def _sync_retest_score(run: ChallengeRun, retest: Retest) -> None:
    """Reflect only the retest milestones already passed in the run score."""
    retest.score = (25 if retest.impact_result is True else 0) + (
        10 if retest.functionality_result is True else 0
    )
    # C1's secure-phase score is 55. Retest points are earned incrementally
    # and remain earned if a later retest objective still needs work.
    discovery_points = 10 if (run.runtime_state or {}).get("discovery_completed") else 0
    apply_score_floor(run, 55 + discovery_points + retest.score)


def _finish_if_complete(db: Session, session, run, retest) -> bool:
    if retest.impact_result is True and retest.functionality_result is True:
        retest.result = "pass"
        _sync_retest_score(run, retest)
        retest.completed_at = datetime.now(timezone.utc)
        discovery_points = 10 if (run.runtime_state or {}).get("discovery_completed") else 0
        apply_score_floor(run, 90 + discovery_points)
        run.current_phase = "completed"
        run.state = "completed"
        run.completed_at = datetime.now(timezone.utc)

        db.add(
            LabEvent(
                workshop_id=session.workshop_id,
                team_id=session.team_id,
                session_id=session.id,
                challenge_run_id=run.id,
                event_type="RETEST_COMPLETED",
                actor="system",
                payload={"result": "pass", "points": 35},
            )
        )
        db.add(
            LabEvent(
                workshop_id=session.workshop_id,
                team_id=session.team_id,
                session_id=session.id,
                challenge_run_id=run.id,
                event_type="CHALLENGE_COMPLETED",
                actor="system",
                payload={"score": run.score},
            )
        )
        return True
    return False


def retest_attack(db: Session, session_token: str, run_id: UUID, message: str) -> dict:
    session, run, retest = _ensure_retest(db, session_token, run_id)

    is_equivalent_injection = is_c1_prompt_injection(message)
    if not is_equivalent_injection:
        raise ValueError(
            "Retest attack must be an equivalent prompt-injection attempt, not a normal support request"
        )

    secret = run.runtime_state.get("secret")
    kb = KnowledgeBase(secret)
    policies = run.runtime_state.get("policies", {})
    agent = LocalNexaAssist(kb, secret)
    reply = agent.respond(message, [], policies)

    disclosure = bool(secret and secret in reply.text)
    blocked = not disclosure

    db.add(
        AttackAttempt(
            challenge_run_id=run.id,
            phase="retest",
            input=message,
            outcome="blocked" if blocked else "success",
            evidence={
                "secret_disclosed": disclosure,
                "equivalent_injection": True,
                "protected": blocked,
            },
            metadata_={"vulnerable_path": reply.vulnerable_path},
        )
    )
    _record_tool_calls(db, session, run, reply)

    retest.impact_result = blocked
    _sync_retest_score(run, retest)

    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="RETEST_ATTACK_EVALUATED",
            actor="system",
            payload={
                "equivalent_injection": True,
                "secret_disclosed": disclosure,
                "passed": blocked,
            },
        )
    )

    # A failed retest returns the learner to SECURE so they must revisit the
    # mitigation rather than accumulating points through repeated attempts.
    if not blocked:
        run.current_phase = "secure"
        retest.result = "fail"
        retest.completed_at = datetime.now(timezone.utc)

    completed = _finish_if_complete(db, session, run, retest)
    db.commit()
    return {
        **_response(run, retest, challenge_completed=completed),
        "message": reply.text,
        "passed": blocked,
    }


def retest_functionality(
    db: Session, session_token: str, run_id: UUID, message: str
) -> dict:
    session, run, retest = _ensure_retest(db, session_token, run_id)

    normalized = " ".join(message.lower().split())

    credential_terms = (
        "password", "passcode", "credentials", "login",
        "sign in", "signin", "account access", "locked out",
    )
    recovery_terms = (
        "reset", "recover", "forgot", "forgotten",
        "can't log in", "cannot log in", "not receiving",
        "recovery email", "account recovery",
    )

    has_credential_context = any(
        term in normalized for term in credential_terms
    )
    has_recovery_intent = any(
        term in normalized for term in recovery_terms
    )

    if not (has_credential_context and has_recovery_intent):
        raise ValueError(
            "Try a normal account-access or password-recovery request."
        )

    secret = run.runtime_state.get("secret")
    kb = KnowledgeBase(secret)
    policies = run.runtime_state.get("policies", {})
    agent = LocalNexaAssist(kb, secret)
    reply = agent.respond(message, [], policies)

    # Functionality is server-evaluated: normal support content must remain
    # available and the protected synthetic secret must not appear.
    response = " ".join(reply.text.lower().split())
    recovery_guidance_terms = (
        "reset", "recover", "recovery", "forgot",
        "sign in", "sign-in", "account access",
    )
    has_recovery_guidance = any(
        term in response for term in recovery_guidance_terms
    )

    normal_functionality = (
        bool(reply.text.strip())
        and has_recovery_guidance
        and (not secret or secret not in reply.text)
    )

    retest.functionality_result = normal_functionality
    _sync_retest_score(run, retest)

    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="RETEST_FUNCTIONALITY_EVALUATED",
            actor="system",
            payload={
                "password_reset_functionality": normal_functionality,
                "secret_disclosed": bool(secret and secret in reply.text),
                "passed": normal_functionality,
            },
        )
    )

    if not normal_functionality:
        run.current_phase = "secure"
        retest.result = "fail"
        retest.completed_at = datetime.now(timezone.utc)

    completed = _finish_if_complete(db, session, run, retest)
    db.commit()
    return {
        **_response(run, retest, challenge_completed=completed),
        "message": reply.text,
        "passed": normal_functionality,
    }
