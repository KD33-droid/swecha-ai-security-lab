from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.workshops import challenge_history


class FakeDB:
    def __init__(self, session=None, rows=None, events=None):
        self.session = session
        self.rows = rows or []
        self.events = events or []
        self.statement = None
        self.event_statement = None

    def scalar(self, statement):
        return self.session

    def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: self.rows)

    def scalars(self, statement):
        self.event_statement = statement
        return SimpleNamespace(all=lambda: self.events)


def test_challenge_history_returns_scores_for_valid_session():
    session_id = uuid4()
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)

    session = SimpleNamespace(id=session_id, status="active")
    run = SimpleNamespace(
        id=run_id,
        challenge_version="1.0",
        current_phase="secure",
        state="active",
        score=65,
        best_score=90,
        reset_count=1,
        started_at=started_at,
        completed_at=None,
    )
    challenge = SimpleNamespace(
        slug="c1",
        name="Challenge 1",
    )
    db = FakeDB(session=session, rows=[(run, challenge)])

    response = challenge_history("valid-token", db)

    assert len(response.items) == 1
    item = response.items[0]
    assert item.run_id == run_id
    assert item.challenge_slug == "c1"
    assert item.score == 65
    assert item.best_score == 90
    assert item.reset_count == 1
    assert item.phase == "secure"


def test_challenge_history_rejects_invalid_session():
    db = FakeDB(session=None)

    with pytest.raises(HTTPException) as exc:
        challenge_history("invalid-token", db)

    assert exc.value.status_code == 401


def test_challenge_history_query_is_scoped_to_session():
    db = FakeDB(session=SimpleNamespace(id=uuid4(), status="active"))

    challenge_history("valid-token", db)

    sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "challenge_runs.session_id =" in sql


def test_challenge_history_includes_saved_reset_attempts():
    session_id = uuid4()
    run_id = uuid4()
    reset_at = datetime.now(timezone.utc)

    session = SimpleNamespace(id=session_id, status="active")
    run = SimpleNamespace(
        id=run_id,
        challenge_version="1.0",
        current_phase="break",
        state="active",
        score=0,
        best_score=85,
        reset_count=1,
        started_at=reset_at,
        completed_at=None,
    )
    challenge = SimpleNamespace(slug="c1", name="Challenge 1")
    event = SimpleNamespace(
        challenge_run_id=run_id,
        timestamp=reset_at,
        payload={
            "attempt_number": 1,
            "attempt_score": 85,
            "best_score": 85,
            "phase": "secure",
            "state": "completed",
        },
    )
    db = FakeDB(
        session=session,
        rows=[(run, challenge)],
        events=[event],
    )

    response = challenge_history("valid-token", db)

    assert len(response.items) == 1
    item = response.items[0]
    assert len(item.attempts) == 1
    attempt = item.attempts[0]
    assert attempt.attempt_number == 1
    assert attempt.score == 85
    assert attempt.best_score == 85
    assert attempt.phase == "secure"
    assert attempt.state == "completed"
    assert attempt.reset_at == reset_at.isoformat()
    assert "lab_events.session_id =" in str(
        db.event_statement.compile(compile_kwargs={"literal_binds": True})
    )
