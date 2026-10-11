"""Shared challenge scoring with persistent hint penalties."""


def apply_score_floor(run, earned_score: int) -> None:
    """Award a gross milestone while preserving all hint deductions."""
    runtime = dict(run.runtime_state or {})
    penalty = max(0, int(runtime.get("hint_penalty_total", 0)))
    current_gross = int(run.score or 0) + penalty
    gross_score = max(current_gross, int(earned_score))
    run.score = max(0, gross_score - penalty)


def apply_hint_penalty(run, penalty: int) -> int:
    """Apply a new hint penalty and return the resulting net score."""
    runtime = dict(run.runtime_state or {})
    old_penalty = max(0, int(runtime.get("hint_penalty_total", 0)))
    gross_score = int(run.score or 0) + old_penalty
    new_penalty = old_penalty + max(0, int(penalty))
    runtime["hint_penalty_total"] = new_penalty
    run.runtime_state = runtime
    run.score = max(0, gross_score - new_penalty)
    return run.score
