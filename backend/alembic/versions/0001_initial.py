"""initial domain schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def uuid_col():
    return postgresql.UUID(as_uuid=True)


def json_col():
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade():
    op.create_table("organizations",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("challenges",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("slug", sa.String(100), nullable=False), sa.Column("version", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("difficulty", sa.String(30), nullable=False),
        sa.Column("category", sa.String(80), nullable=False), sa.Column("estimated_minutes", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("manifest", json_col(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", "version", name="uq_challenge_slug_version"))
    op.create_table("workshops",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("organization_id", uuid_col(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("slug", sa.String(100), nullable=False), sa.Column("join_code", sa.String(32), nullable=False, unique=True),
        sa.Column("description", sa.Text()), sa.Column("status", sa.String(30), nullable=False), sa.Column("team_size", sa.Integer(), nullable=False),
        sa.Column("participant_limit", sa.Integer(), nullable=False), sa.Column("leaderboard_enabled", sa.Boolean(), nullable=False), sa.Column("hints_enabled", sa.Boolean(), nullable=False),
        sa.Column("configuration", json_col(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("workshop_challenges",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("workshop_id", uuid_col(), sa.ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_id", uuid_col(), sa.ForeignKey("challenges.id"), nullable=False), sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("required", sa.Boolean(), nullable=False), sa.Column("configuration", json_col(), nullable=False),
        sa.UniqueConstraint("workshop_id", "challenge_id", name="uq_workshop_challenge"))
    op.create_table("teams",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("workshop_id", uuid_col(), sa.ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("join_code", sa.String(32), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.UniqueConstraint("workshop_id", "join_code", name="uq_team_join_code"))
    op.create_table("participants",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("workshop_id", uuid_col(), sa.ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", uuid_col(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    op.create_table("sessions",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("workshop_id", uuid_col(), sa.ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", uuid_col(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("participant_id", uuid_col(), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    op.create_table("challenge_runs",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("session_id", uuid_col(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("challenge_id", uuid_col(), sa.ForeignKey("challenges.id"), nullable=False), sa.Column("challenge_version", sa.String(30), nullable=False),
        sa.Column("state", sa.String(30), nullable=False), sa.Column("current_phase", sa.String(30), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("reset_count", sa.Integer(), nullable=False), sa.Column("runtime_state", json_col(), nullable=False), sa.Column("score", sa.Integer(), nullable=False))
    op.create_table("attack_attempts",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("challenge_run_id", uuid_col(), sa.ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase", sa.String(30), nullable=False), sa.Column("input", sa.Text(), nullable=False), sa.Column("outcome", sa.String(50), nullable=False), sa.Column("evidence", json_col(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("metadata", json_col(), nullable=False))
    op.create_table("tool_calls",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("challenge_run_id", uuid_col(), sa.ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool", sa.String(100), nullable=False), sa.Column("arguments", json_col(), nullable=False), sa.Column("authorization_result", sa.String(30), nullable=False),
        sa.Column("execution_result", json_col(), nullable=False), sa.Column("risk_level", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("policy_changes",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("challenge_run_id", uuid_col(), sa.ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy", sa.String(100), nullable=False), sa.Column("old_configuration", json_col(), nullable=False), sa.Column("new_configuration", json_col(), nullable=False),
        sa.Column("changed_by", uuid_col(), sa.ForeignKey("participants.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("retests",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("challenge_run_id", uuid_col(), sa.ForeignKey("challenge_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attack_reference", uuid_col(), sa.ForeignKey("attack_attempts.id")), sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("result", sa.String(30)), sa.Column("impact_result", sa.Boolean()), sa.Column("functionality_result", sa.Boolean()), sa.Column("score", sa.Integer(), nullable=False))
    op.create_table("lab_events",
        sa.Column("id", uuid_col(), primary_key=True), sa.Column("workshop_id", uuid_col(), sa.ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", uuid_col(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("session_id", uuid_col(), sa.ForeignKey("sessions.id", ondelete="CASCADE")),
        sa.Column("challenge_run_id", uuid_col(), sa.ForeignKey("challenge_runs.id", ondelete="CASCADE")), sa.Column("event_type", sa.String(50), nullable=False), sa.Column("actor", sa.String(50), nullable=False),
        sa.Column("payload", json_col(), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    for table in ["lab_events", "retests", "policy_changes", "tool_calls", "attack_attempts", "challenge_runs", "sessions", "participants", "teams", "workshop_challenges", "workshops", "challenges", "organizations"]:
        op.drop_table(table)
