from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.challenge_timer import (
    CHALLENGE_DURATION,
    WARNING_THRESHOLD,
    enforce_deadline,
    remaining_seconds,
    start_deadline,
    timer_status,
)


class FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_new_deadline_is_75_minutes():
    now = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
    assert start_deadline(now) == now + timedelta(minutes=75)


def test_remaining_seconds_and_expiry_boundary():
    now = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
    deadline = now + CHALLENGE_DURATION
    assert remaining_seconds(deadline, now) == 4500
    assert remaining_seconds(deadline, deadline) == 0
    assert remaining_seconds(deadline, deadline + timedelta(seconds=1)) == 0


def test_warning_starts_at_ten_minutes():
    now = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
    run = SimpleNamespace(deadline_at=now + WARNING_THRESHOLD, state="active")
    result = timer_status(run, now)
    assert result["timer_warning"] is True
    assert result["remaining_seconds"] == 600


def test_completed_run_is_not_expired():
    run = SimpleNamespace(state="completed", deadline_at=None)
    enforce_deadline(FakeDB(), run)


def test_expired_run_rejects_actions():
    run = SimpleNamespace(
        state="expired",
        deadline_at=datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc),
        current_phase="expired",
    )
    with pytest.raises(ValueError, match="time has expired"):
        enforce_deadline(FakeDB(), run)


def test_expiry_preserves_score_and_commits():
    now = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
    db = FakeDB()
    run = SimpleNamespace(
        state="active",
        deadline_at=now - timedelta(seconds=1),
        current_phase="break",
        score=35,
        best_score=10,
    )

    with pytest.raises(ValueError, match="time has expired"):
        enforce_deadline(db, run, now)

    assert run.state == "expired"
    assert run.current_phase == "expired"
    assert run.score == 35
    assert run.best_score == 35
    assert db.commits == 1
