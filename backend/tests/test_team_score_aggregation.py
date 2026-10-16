import pytest

from app.api.organizer_monitoring import aggregate_team_scores


def test_team_total_is_average_of_participant_totals():
    total, challenges = aggregate_team_scores([
        {"c1": 100, "c2": 80, "c3": 60},
        {"c1": 80, "c2": 60, "c3": 40},
        {"c1": 60, "c2": 40, "c3": 20},
    ])

    assert total == 180
    assert challenges == [
        {"challenge_slug": "c1", "best_score": 80},
        {"challenge_slug": "c2", "best_score": 60},
        {"challenge_slug": "c3", "best_score": 40},
    ]


def test_missing_challenge_scores_count_as_zero():
    total, challenges = aggregate_team_scores([
        {"c1": 100, "c2": 60},
        {"c1": 80},
    ])

    assert total == 120
    assert challenges == [
        {"challenge_slug": "c1", "best_score": 90},
        {"challenge_slug": "c2", "best_score": 30},
    ]


def test_larger_team_does_not_gain_points_from_member_count_alone():
    small_team_total, _ = aggregate_team_scores([
        {"c1": 90, "c2": 60},
    ])
    larger_team_total, _ = aggregate_team_scores([
        {"c1": 90, "c2": 60},
        {"c1": 90, "c2": 60},
        {"c1": 90, "c2": 60},
    ])

    assert small_team_total == larger_team_total == 150


def test_empty_team_has_zero_score():
    assert aggregate_team_scores([]) == (0, [])


def test_fractional_team_averages_are_rounded_to_two_decimals():
    total, challenges = aggregate_team_scores([
        {"c1": 80},
        {"c1": 71},
        {"c1": 70},
    ])

    assert total == 73.67
    assert challenges == [
        {"challenge_slug": "c1", "best_score": 73.67},
    ]
