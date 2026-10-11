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

        team_best_scores = {}
        team_challenges = []

        for participant in participants:
            sessions = db.scalars(
                select(LabSession)
                .where(
                    LabSession.participant_id == participant.id,
                    LabSession.workshop_id == workshop.id,
                )
            ).all()

            participant_runs = []
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
                    team_best_scores[challenge.slug] = max(
                        team_best_scores.get(challenge.slug, 0),
                        score,
                    )

                    participant_runs.append({
                        "run_id": str(run.id),
                        "challenge_slug": challenge.slug,
                        "challenge_name": challenge.name,
                        "score": score,
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

            team_challenges.extend(participant_runs)

        leaderboard.append({
            "team_id": str(team.id),
            "team_name": team.name,
            "participant_count": len(participants),
            "total_score": sum(team_best_scores.values()),
            "challenge_scores": [
                {"challenge_slug": slug, "best_score": score}
                for slug, score in sorted(team_best_scores.items())
            ],
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
