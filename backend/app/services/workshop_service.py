from __future__ import annotations

import secrets
import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Challenge, ChallengeRun, LabEvent, LabSession, Participant, Team, Workshop, WorkshopChallenge

from app.services.challenge_timer import CHALLENGE_DURATION, enforce_deadline, remaining_seconds, start_deadline, utc_now


def join_workshop(
    db: Session,
    workshop_code: str,
    team_code: str,
    display_name: str,
    session_token: str | None = None,
):
    workshop = db.scalar(
        select(Workshop).where(
            Workshop.join_code == workshop_code,
            Workshop.status == "active",
        )
    )
    if not workshop:
        raise ValueError("Invalid or inactive workshop code")

    team = db.scalar(
        select(Team).where(
            Team.workshop_id == workshop.id,
            Team.join_code == team_code,
            Team.status == "active",
        )
    )
    if not team:
        raise ValueError("Invalid or inactive team code")

    # Returning participant: restore the existing session.
    # This check happens BEFORE capacity checks so a full team
    # does not prevent an existing member from reconnecting.
    if session_token:
        existing_session = db.scalar(
            select(LabSession).where(
                LabSession.session_token == session_token,
                LabSession.workshop_id == workshop.id,
                LabSession.team_id == team.id,
                LabSession.status == "active",
            )
        )

        if existing_session:
            participant = db.scalar(
                select(Participant).where(
                    Participant.id == existing_session.participant_id,
                    Participant.workshop_id == workshop.id,
                    Participant.team_id == team.id,
                )
            )

            if participant:
                participant.last_seen_at = func.now()
                existing_session.last_seen_at = func.now()

                db.add(
                    LabEvent(
                        workshop_id=workshop.id,
                        team_id=team.id,
                        session_id=existing_session.id,
                        event_type="SESSION_REJOINED",
                        actor="participant",
                        payload={"display_name": participant.display_name},
                    )
                )

                db.commit()

                return workshop, team, participant, existing_session

    # New participant: normal capacity checks apply.
    participant_count = (
        db.scalar(
            select(func.count())
            .select_from(Participant)
            .where(Participant.workshop_id == workshop.id)
        )
        or 0
    )

    if participant_count >= workshop.participant_limit:
        raise ValueError("Workshop participant limit reached")

    team_count = (
        db.scalar(
            select(func.count())
            .select_from(Participant)
            .where(Participant.team_id == team.id)
        )
        or 0
    )

    if team_count >= workshop.team_size:
        raise ValueError("Team is full")

    participant = Participant(
        workshop_id=workshop.id,
        team_id=team.id,
        display_name=display_name.strip(),
        role="student",
    )
    db.add(participant)
    db.flush()

    session = LabSession(
        workshop_id=workshop.id,
        team_id=team.id,
        participant_id=participant.id,
        session_token=secrets.token_urlsafe(32),
    )
    db.add(session)
    db.flush()

    db.add(
        LabEvent(
            workshop_id=workshop.id,
            team_id=team.id,
            session_id=session.id,
            event_type="SESSION_STARTED",
            actor="participant",
            payload={"display_name": participant.display_name},
        )
    )

    db.commit()

    return workshop, team, participant, session

def start_challenge(db: Session, session_token: str, challenge_slug: str):
    # Serialize first-start requests so simultaneous clicks cannot create
    # competing deadlines for the same participant.
    session = db.scalar(
        select(LabSession)
        .where(
            LabSession.session_token == session_token,
            LabSession.status == "active",
        )
        .with_for_update()
    )
    if not session:
        raise ValueError("Invalid session token")

    challenge = db.scalar(
        select(Challenge)
        .join(WorkshopChallenge, WorkshopChallenge.challenge_id == Challenge.id)
        .where(
            WorkshopChallenge.workshop_id == session.workshop_id,
            WorkshopChallenge.enabled.is_(True),
            Challenge.slug == challenge_slug,
            Challenge.status == "active",
        )
    )
    if not challenge:
        raise ValueError("Challenge is not enabled for this workshop")

    now = utc_now()
    if session.deadline_at is None:
        session.started_at = now
        session.deadline_at = start_deadline(now)

    seconds_left = remaining_seconds(session.deadline_at, now)
    if seconds_left is None or seconds_left <= 0:
        # Persist the session deadline if this was the first request, but
        # never create another run once the shared timer has expired.
        db.commit()
        raise ValueError("Challenge time has expired")

    from app.services.challenge_runtime import initial_runtime

    runtime_state = initial_runtime(challenge.slug)
    run = ChallengeRun(
        session_id=session.id,
        challenge_id=challenge.id,
        challenge_version=challenge.version,
        state="active",
        current_phase="break",
        runtime_state=runtime_state,
        score=0,
        deadline_at=session.deadline_at,
    )
    db.add(run)
    db.flush()
    db.add(
        LabEvent(
            workshop_id=session.workshop_id,
            team_id=session.team_id,
            session_id=session.id,
            challenge_run_id=run.id,
            event_type="CHALLENGE_STARTED",
            actor="participant",
            payload={"challenge": challenge.slug, "version": challenge.version},
        )
    )
    db.commit()
    return run, challenge


def run_challenge_slug(db: Session, run: ChallengeRun) -> str:
    challenge = db.scalar(select(Challenge).where(Challenge.id == run.challenge_id))
    if not challenge:
        raise ValueError("Challenge definition not found")
    return challenge.slug


def reset_challenge_run(db: Session, session_token: str, run_id):
    session = db.scalar(select(LabSession).where(LabSession.session_token == session_token, LabSession.status == "active"))
    if not session:
        raise ValueError("Invalid session token")
    run = db.scalar(select(ChallengeRun).where(ChallengeRun.id == run_id, ChallengeRun.session_id == session.id))
    if not run:
        raise ValueError("Challenge run not found")

    enforce_deadline(db, run)

    from app.services.score_service import update_best_score

    # Snapshot the attempt before reset clears its current score and phase.
    attempt_score = int(run.score or 0)
    update_best_score(run)
    attempt_best_score = int(run.best_score or 0)
    attempt_phase = run.current_phase
    attempt_state = run.state
    attempt_number = (run.reset_count or 0) + 1

    from app.services.challenge_runtime import initial_runtime
    runtime_state = initial_runtime(run_challenge_slug(db, run))
    run.runtime_state = runtime_state
    run.state = "active"
    run.current_phase = "break"
    run.score = 0
    run.completed_at = None
    run.reset_count = (run.reset_count or 0) + 1

    db.add(LabEvent(
        workshop_id=session.workshop_id, team_id=session.team_id, session_id=session.id,
        challenge_run_id=run.id, event_type="CHALLENGE_RESET", actor="participant",
        payload={
            "reset_count": run.reset_count,
            "attempt_number": attempt_number,
            "attempt_score": attempt_score,
            "best_score": attempt_best_score,
            "phase": attempt_phase,
            "state": attempt_state,
        },
    ))
    db.commit()
    return run
