"""Server-authoritative countdown and expiry rules for participant sessions."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChallengeRun, LabSession
from app.services.score_service import update_best_score

CHALLENGE_DURATION = timedelta(minutes=75)
WARNING_THRESHOLD = timedelta(minutes=10)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def start_deadline(now: datetime | None = None) -> datetime:
    return (now or utc_now()) + CHALLENGE_DURATION


def remaining_seconds(
    deadline_at: datetime | None,
    now: datetime | None = None,
) -> int | None:
    if deadline_at is None:
        return None

    current = now or utc_now()
    if deadline_at.tzinfo is None:
        deadline_at = deadline_at.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    return max(0, int((deadline_at - current).total_seconds()))


def effective_deadline(db, run: ChallengeRun):
    """Resolve the session deadline, falling back to the legacy run field."""
    session_id = getattr(run, "session_id", None)
    if session_id is not None and hasattr(db, "scalar"):
        try:
            session = db.scalar(
                select(LabSession).where(LabSession.id == session_id)
            )
        except (AttributeError, TypeError):
            session = None
        if session is not None and session.deadline_at is not None:
            return session.deadline_at

    return getattr(run, "deadline_at", None)


def timer_status(
    run: ChallengeRun,
    now: datetime | None = None,
    db=None,
) -> dict:
    deadline = (
        effective_deadline(db, run)
        if db is not None
        else getattr(run, "deadline_at", None)
    )
    seconds = remaining_seconds(deadline, now)
    return {
        "deadline_at": deadline.isoformat() if deadline else None,
        "remaining_seconds": seconds,
        "timer_warning": (
            seconds is not None
            and 0 < seconds <= int(WARNING_THRESHOLD.total_seconds())
        ),
    }


def enforce_deadline(
    db: Session,
    run: ChallengeRun,
    now: datetime | None = None,
) -> None:
    """Persist expiry before rejecting the attempted action."""
    if run.state == "completed":
        return

    if run.state == "expired":
        raise ValueError("Challenge time has expired")

    deadline = effective_deadline(db, run)
    seconds = remaining_seconds(deadline, now)

    if seconds is None:
        raise ValueError("Challenge timer is not initialized")

    if deadline is not None and getattr(run, "deadline_at", None) != deadline:
        run.deadline_at = deadline

    if seconds <= 0:
        update_best_score(run)
        run.state = "expired"
        run.current_phase = "expired"
        db.commit()
        raise ValueError("Challenge time has expired")


def refresh_expiry(
    db: Session,
    run: ChallengeRun,
    now: datetime | None = None,
) -> bool:
    """Persist an overdue run as expired; return whether it is expired."""
    if run.state == "completed":
        return False

    if run.state == "expired":
        return True

    deadline = effective_deadline(db, run)
    seconds = remaining_seconds(deadline, now)
    if seconds is None or seconds > 0:
        return False

    if deadline is not None and getattr(run, "deadline_at", None) != deadline:
        run.deadline_at = deadline

    update_best_score(run)
    run.state = "expired"
    run.current_phase = "expired"
    db.commit()
    return True
