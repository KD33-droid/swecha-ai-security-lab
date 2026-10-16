"""Persist best score across challenge resets."""

from alembic import op
import sqlalchemy as sa

revision = "0002_best_score"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "challenge_runs",
        sa.Column("best_score", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("challenge_runs", "best_score")
