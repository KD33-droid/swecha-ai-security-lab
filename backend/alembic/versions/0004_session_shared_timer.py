"""Add a shared 75-minute timer to participant sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0004_session_shared_timer"
down_revision = "0003_challenge_run_deadline"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sessions",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Preserve existing limits; use the earliest run deadline for each session.
    op.execute("""
        UPDATE sessions AS s
        SET started_at = x.first_started_at,
            deadline_at = x.first_deadline_at
        FROM (
            SELECT session_id,
                   MIN(started_at) AS first_started_at,
                   MIN(deadline_at) AS first_deadline_at
            FROM challenge_runs
            GROUP BY session_id
        ) AS x
        WHERE s.id = x.session_id
    """)

    # Keep legacy run-level deadline fields consistent with the shared timer.
    op.execute("""
        UPDATE challenge_runs AS r
        SET deadline_at = s.deadline_at
        FROM sessions AS s
        WHERE r.session_id = s.id
          AND s.deadline_at IS NOT NULL
    """)


def downgrade():
    op.drop_column("sessions", "deadline_at")
    op.drop_column("sessions", "started_at")
