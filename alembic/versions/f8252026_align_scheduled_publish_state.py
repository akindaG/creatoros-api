"""align scheduled post publish-state constraint

Revision ID: f8252026
Revises: e8252026
"""

from alembic import op


revision = "f8252026"
down_revision = "e8252026"
branch_labels = None
depends_on = None


ALLOWED_STATES = (
    "scheduled",
    "queued",
    "published",
    "failed",
    "ready_to_share",
    "shared",
)


def upgrade():
    op.execute(
        "ALTER TABLE scheduled_posts "
        "DROP CONSTRAINT IF EXISTS scheduled_posts_publish_state_check"
    )
    allowed = ", ".join(f"'{state}'" for state in ALLOWED_STATES)
    # Production contains legacy schedule-state values created before the
    # current state machine was standardized. NOT VALID preserves those old
    # rows while immediately enforcing the current state set for new/updated
    # rows. This lets the deployment recover without rewriting user data.
    op.execute(
        "ALTER TABLE scheduled_posts "
        "ADD CONSTRAINT scheduled_posts_publish_state_check "
        f"CHECK (publish_state IN ({allowed})) NOT VALID"
    )


def downgrade():
    # Older CreatorOS databases accepted only the stable automatic-publishing
    # states. Normalize newer manual-share/transient states before restoring
    # that narrower constraint.
    op.execute(
        "UPDATE scheduled_posts SET publish_state = 'scheduled' "
        "WHERE publish_state IN ('queued', 'ready_to_share')"
    )
    op.execute(
        "UPDATE scheduled_posts SET publish_state = 'published' "
        "WHERE publish_state = 'shared'"
    )
    op.execute(
        "ALTER TABLE scheduled_posts "
        "DROP CONSTRAINT IF EXISTS scheduled_posts_publish_state_check"
    )
    op.execute(
        "ALTER TABLE scheduled_posts "
        "ADD CONSTRAINT scheduled_posts_publish_state_check "
        "CHECK (publish_state IN ('scheduled', 'published', 'failed')) NOT VALID"
    )
