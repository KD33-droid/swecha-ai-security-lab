from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Challenge, Organization, Team, Workshop, WorkshopChallenge
from app.services.challenge_registry import ChallengeRegistry

router = APIRouter(prefix="/dev", tags=["development"])


@router.post("/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    if settings.environment != "development":
        return {"status": "disabled"}

    org = db.scalar(
        select(Organization).where(Organization.slug == "swecha")
    )

    if not org:
        org = Organization(name="Swecha", slug="swecha")
        db.add(org)
        db.flush()

    registry = ChallengeRegistry()

    slugs = [
        "ignore-the-rules",
        "poisoned-doc",
        "too-much-power",
        "whose-data",
    ]

    challenges = []

    for slug in slugs:
        manifest = registry.get(slug)
        meta = manifest["metadata"]

        challenge = db.scalar(
            select(Challenge).where(
                Challenge.slug == slug,
                Challenge.version == manifest["version"],
            )
        )

        if not challenge:
            challenge = Challenge(
                slug=slug,
                version=manifest["version"],
                name=meta["name"],
                description=meta["description"],
                difficulty=meta["difficulty"],
                category=meta["category"],
                estimated_minutes=meta["estimated_minutes"],
                manifest=manifest,
            )
            db.add(challenge)
            db.flush()

        challenges.append(challenge)

    workshop = db.scalar(
        select(Workshop).where(
            Workshop.join_code == "DEV-LAB"
        )
    )

    if not workshop:
        workshop = Workshop(
            organization_id=org.id,
            name="AI Security Lab — Development",
            slug="dev-workshop",
            join_code="DEV-LAB",
            description="Local development workshop",
            team_size=3,
            participant_limit=150,
            configuration={"mode": "break-secure-retest"},
        )
        db.add(workshop)
        db.flush()

    # Development teams
    for name, code in [
        ("Team Alpha", "ALPHA"),
        ("Team Beta", "BETA"),
        ("Team Gamma", "GAMMA"),
    ]:
        existing_team = db.scalar(
            select(Team).where(
                Team.workshop_id == workshop.id,
                Team.join_code == code,
            )
        )

        if not existing_team:
            db.add(
                Team(
                    workshop_id=workshop.id,
                    name=name,
                    join_code=code,
                )
            )

    for i, challenge in enumerate(challenges, 1):
        link = db.scalar(
            select(WorkshopChallenge).where(
                WorkshopChallenge.workshop_id == workshop.id,
                WorkshopChallenge.challenge_id == challenge.id,
            )
        )

        if not link:
            db.add(
                WorkshopChallenge(
                    workshop_id=workshop.id,
                    challenge_id=challenge.id,
                    display_order=i,
                    configuration={},
                )
            )

    db.commit()

    return {
        "status": "ok",
        "workshop_code": workshop.join_code,
        "team_code": "ALPHA",
        "challenges": [c.slug for c in challenges],
    }
