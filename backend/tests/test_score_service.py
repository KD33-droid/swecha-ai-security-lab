from types import SimpleNamespace

from app.services.score_service import (
    apply_hint_penalty,
    apply_score_floor,
    update_best_score,
)


def make_run(score=0, best_score=0, runtime_state=None):
    return SimpleNamespace(
        score=score,
        best_score=best_score,
        runtime_state=runtime_state or {},
    )


def test_score_floor_updates_best_score():
    run = make_run()

    apply_score_floor(run, 40)

    assert run.score == 40
    assert run.best_score == 40


def test_best_score_never_decreases():
    run = make_run(score=25, best_score=80)

    assert update_best_score(run) == 80
    assert run.best_score == 80


def test_hint_penalty_reduces_current_score_but_preserves_best():
    run = make_run(score=80, best_score=80)

    result = apply_hint_penalty(run, 15)

    assert result == 65
    assert run.score == 65
    assert run.best_score == 80


def test_new_higher_score_replaces_previous_best():
    run = make_run(score=65, best_score=80)

    apply_score_floor(run, 95)

    assert run.score == 95
    assert run.best_score == 95


def test_hint_penalty_is_cumulative():
    run = make_run(score=80)

    apply_hint_penalty(run, 10)
    apply_hint_penalty(run, 15)

    assert run.score == 55
    assert run.best_score == 80
    assert run.runtime_state["hint_penalty_total"] == 25


def test_resetting_current_score_does_not_erase_best():
    run = make_run(score=75)

    update_best_score(run)
    run.score = 0

    assert run.score == 0
    assert run.best_score == 75
