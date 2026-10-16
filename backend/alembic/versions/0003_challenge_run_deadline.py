"""Persist challenge-run timer deadlines."""

from alembic import op
import sqlalchemy as sa

revision = "0003_challenge_run_deadline"
down_revision = "0002_best_score"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "challenge_runs",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE challenge_runs "
        "SET deadline_at = started_at + INTERVAL '75 minutes' "
        "WHERE deadline_at IS NULL"
    )
    op.alter_column(
        "challenge_runs",
        "deadline_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade():
    op.drop_column("challenge_runs", "deadline_at")
