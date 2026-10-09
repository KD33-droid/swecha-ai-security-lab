from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def json_column(default: Any = dict) -> Mapped[dict]:
    return mapped_column(JSONB, nullable=False, default=default)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)


class Workshop(TimestampMixin, Base):
    __tablename__ = "workshops"
    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    join_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    team_size: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    participant_limit: Mapped[int] = mapped_column(Integer, default=150, nullable=False)
    leaderboard_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hints_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration: Mapped[dict] = json_column()

    organization: Mapped[Organization] = relationship()
    challenges: Mapped[list[WorkshopChallenge]] = relationship(back_populates="workshop", cascade="all, delete-orphan")
    teams: Mapped[list[Team]] = relationship(back_populates="workshop", cascade="all, delete-orphan")


class Challenge(TimestampMixin, Base):
    __tablename__ = "challenges"
    __table_args__ = (UniqueConstraint("slug", "version", name="uq_challenge_slug_version"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    manifest: Mapped[dict] = json_column()


class WorkshopChallenge(Base):
    __tablename__ = "workshop_challenges"
    __table_args__ = (UniqueConstraint("workshop_id", "challenge_id", name="uq_workshop_challenge"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuration: Mapped[dict] = json_column()

    workshop: Mapped[Workshop] = relationship(back_populates="challenges")
    challenge: Mapped[Challenge] = relationship()


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("workshop_id", "join_code", name="uq_team_join_code"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    join_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)

    workshop: Mapped[Workshop] = relationship(back_populates="teams")
    participants: Mapped[list[Participant]] = relationship(back_populates="team", cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[uuid.UUID] = uuid_pk()
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="student", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    team: Mapped[Team] = relationship(back_populates="participants")


class LabSession(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = uuid_pk()
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChallengeRun(Base):
    __tablename__ = "challenge_runs"
    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    challenge_version: Mapped[str] = mapped_column(String(30), nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    current_phase: Mapped[str] = mapped_column(String(30), default="break", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runtime_state: Mapped[dict] = json_column()
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AttackAttempt(Base):
    __tablename__ = "attack_attempts"
    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence: Mapped[dict] = json_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments: Mapped[dict] = json_column()
    authorization_result: Mapped[str] = mapped_column(String(30), nullable=False)
    execution_result: Mapped[dict] = json_column()
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PolicyChange(Base):
    __tablename__ = "policy_changes"
    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False)
    policy: Mapped[str] = mapped_column(String(100), nullable=False)
    old_configuration: Mapped[dict] = json_column()
    new_configuration: Mapped[dict] = json_column()
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("participants.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Retest(Base):
    __tablename__ = "retests"
    id: Mapped[uuid.UUID] = uuid_pk()
    challenge_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False)
    attack_reference: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attack_attempts.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(String(30))
    impact_result: Mapped[bool | None] = mapped_column(Boolean)
    functionality_result: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LabEvent(Base):
    __tablename__ = "lab_events"
    id: Mapped[uuid.UUID] = uuid_pk()
    workshop_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    challenge_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("challenge_runs.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = json_column()
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
