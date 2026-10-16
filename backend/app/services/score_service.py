"""Shared challenge scoring with persistent hint penalties and best scores."""


def update_best_score(run) -> int:
    """Retain the highest net score reached across resets and retries."""
    current = max(0, int(getattr(run, "score", 0) or 0))
    previous_best = max(0, int(getattr(run, "best_score", 0) or 0))
    run.best_score = max(previous_best, current)
    return run.best_score


def apply_score_floor(run, earned_score: int) -> None:
    """Award a gross milestone while preserving all hint deductions."""
    runtime = dict(run.runtime_state or {})
    penalty = max(0, int(runtime.get("hint_penalty_total", 0)))
    current_gross = int(run.score or 0) + penalty
    gross_score = max(current_gross, int(earned_score))
    run.score = max(0, gross_score - penalty)
    update_best_score(run)


def apply_hint_penalty(run, penalty: int) -> int:
    """Apply a new hint penalty and retain the historical best score."""
    runtime = dict(run.runtime_state or {})
    update_best_score(run)
    old_penalty = max(0, int(runtime.get("hint_penalty_total", 0)))
    gross_score = int(run.score or 0) + old_penalty
    new_penalty = old_penalty + max(0, int(penalty))
    runtime["hint_penalty_total"] = new_penalty
    run.runtime_state = runtime
    run.score = max(0, gross_score - new_penalty)
    return run.score
