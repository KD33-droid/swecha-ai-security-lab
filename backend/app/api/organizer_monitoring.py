from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.organizer_auth import require_staff
from app.db.session import get_db
from app.models import (
    Challenge,
    ChallengeRun,
    LabSession,
    Participant,
    Team,
    Workshop,
)

router = APIRouter(
    prefix="/organizer/workshops",
    tags=["organizer-monitoring"],
)


def aggregate_team_scores(participant_scores: list[dict[str, int]]):
    """Average participant totals and per-challenge best scores.

    Missing challenge scores count as zero. Each participant contributes
    their best score for each challenge, not the sum of repeated runs.
    """
    participant_count = len(participant_scores)
    if participant_count == 0:
        return 0, []

    challenge_slugs = sorted({
        slug
        for scores in participant_scores
        for slug in scores
    })

    challenge_scores = [
        {
            "challenge_slug": slug,
            "best_score": round(
                sum(scores.get(slug, 0) for scores in participant_scores)
                / participant_count,
                2,
            ),
        }
        for slug in challenge_slugs
    ]

    participant_totals = [
        sum(scores.values())
        for scores in participant_scores
    ]
    total_score = round(sum(participant_totals) / participant_count, 2)
    return total_score, challenge_scores


@router.get("/{workshop_id}/monitoring")
def workshop_monitoring(
    workshop_id: UUID,
    staff_role: str = Depends(require_staff),
    db: Session = Depends(get_db),
):
    workshop = db.scalar(
        select(Workshop).where(Workshop.id == workshop_id)
    )
    if not workshop:
        raise HTTPException(status_code=404, detail="Workshop not found")

    teams = db.scalars(
        select(Team)
        .where(Team.workshop_id == workshop.id)
        .order_by(Team.name)
    ).all()

    leaderboard = []
    activity = []

    for team in teams:
        participants = db.scalars(
            select(Participant)
            .where(
                Participant.workshop_id == workshop.id,
                Participant.team_id == team.id,
            )
            .order_by(Participant.display_name)
        ).all()

        participant_best_scores = []

        for participant in participants:
            sessions = db.scalars(
                select(LabSession)
                .where(
                    LabSession.participant_id == participant.id,
                    LabSession.workshop_id == workshop.id,
                )
            ).all()

            participant_runs = []
            individual_best_scores = {}
            for session in sessions:
                runs = db.execute(
                    select(ChallengeRun, Challenge)
                    .join(Challenge, Challenge.id == ChallengeRun.challenge_id)
                    .where(ChallengeRun.session_id == session.id)
                    .order_by(ChallengeRun.started_at.desc())
                ).all()

                for run, challenge in runs:
                    runtime = dict(run.runtime_state or {})
                    penalty = max(0, int(runtime.get("hint_penalty_total", 0)))
                    revealed = runtime.get("hints_revealed", [])
                    hint_count = (
                        len({
                            item.get("level")
                            for item in revealed
                            if isinstance(item, dict)
                            and item.get("level") in (1, 2, 3)
                        })
                        if isinstance(revealed, list)
                        else 0
                    )

                    score = max(0, int(run.score or 0))
                    best_score = max(score, int(run.best_score or 0))
                    individual_best_scores[challenge.slug] = max(
                        individual_best_scores.get(challenge.slug, 0),
                        best_score,
                    )

                    participant_runs.append({
                        "run_id": str(run.id),
                        "challenge_slug": challenge.slug,
                        "challenge_name": challenge.name,
                        "score": score,
                        "best_score": best_score,
                        "phase": run.current_phase,
                        "state": run.state,
                        "started_at": (
                            run.started_at.isoformat()
                            if run.started_at else None
                        ),
                        "completed_at": (
                            run.completed_at.isoformat()
                            if run.completed_at else None
                        ),
                        "reset_count": int(run.reset_count or 0),
                        "hint_count": hint_count,
                        "hint_penalty": penalty,
                    })

            participant_best_scores.append(individual_best_scores)

            latest_runs = {}
            for run_info in participant_runs:
                slug = run_info["challenge_slug"]
                if slug not in latest_runs:
                    latest_runs[slug] = run_info

            activity.append({
                "participant_id": str(participant.id),
                "display_name": participant.display_name,
                "team_id": str(team.id),
                "team_name": team.name,
                "last_seen_at": (
                    participant.last_seen_at.isoformat()
                    if participant.last_seen_at else None
                ),
                "challenges": list(latest_runs.values()),
            })


        total_score, challenge_scores = aggregate_team_scores(
            participant_best_scores
        )
        leaderboard.append({
            "team_id": str(team.id),
            "team_name": team.name,
            "participant_count": len(participants),
            "total_score": total_score,
            "challenge_scores": challenge_scores,
        })

    leaderboard.sort(
        key=lambda item: (-item["total_score"], item["team_name"].lower())
    )
    for rank, team in enumerate(leaderboard, start=1):
        team["rank"] = rank

    return {
        "workshop": {
            "id": str(workshop.id),
            "name": workshop.name,
            "status": workshop.status,
            "leaderboard_enabled": workshop.leaderboard_enabled,
        },
        "staff_role": staff_role,
        "leaderboard": leaderboard,
        "participants": activity,
    }

@router.get("")
def list_workshops(
    staff_role: str = Depends(require_staff),
    db: Session = Depends(get_db),
):
    workshops = db.scalars(
        select(Workshop).order_by(Workshop.name)
    ).all()

    return {
        "items": [
            {
                "id": str(workshop.id),
                "name": workshop.name,
                "status": workshop.status,
                "leaderboard_enabled": workshop.leaderboard_enabled,
            }
            for workshop in workshops
        ],
        "staff_role": staff_role,
    }
