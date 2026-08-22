"""complete MVP backend tables

Revision ID: a8212026
Revises: 027c6c3901fa
"""
from alembic import op

revision = "a8212026"
down_revision = "027c6c3901fa"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_posts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id uuid NOT NULL UNIQUE REFERENCES posts(id) ON DELETE CASCADE,
        schedule_time timestamptz NOT NULL,
        publish_state varchar(30) NOT NULL DEFAULT 'scheduled',
        platform varchar(20) NOT NULL
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_time ON scheduled_posts(schedule_time)")
    op.execute("""
    CREATE TABLE IF NOT EXISTS analytics (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        followers integer NOT NULL DEFAULT 0,
        reach integer NOT NULL DEFAULT 0,
        likes integer NOT NULL DEFAULT 0,
        comments integer NOT NULL DEFAULT 0,
        shares integer NOT NULL DEFAULT 0,
        engagement_rate numeric(7,2) NOT NULL DEFAULT 0,
        captured_at timestamptz NOT NULL DEFAULT now()
    )
    """)
    op.execute("ALTER TABLE analytics ADD COLUMN IF NOT EXISTS followers integer NOT NULL DEFAULT 0")
    op.execute("CREATE INDEX IF NOT EXISTS idx_analytics_post_id ON analytics(post_id)")
    op.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        recommendation_text text NOT NULL,
        type varchar(50) NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_user_id ON recommendations(user_id)")
    op.execute("""
    CREATE TABLE IF NOT EXISTS ai_generation_logs (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        ai_type varchar(50) NOT NULL,
        input_text text NOT NULL,
        output_text text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_logs_user_id ON ai_generation_logs(user_id)")
    op.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title varchar(150) NOT NULL,
        message text NOT NULL,
        is_read boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_generation_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS recommendations CASCADE")
    op.execute("DROP TABLE IF EXISTS analytics CASCADE")
    op.execute("DROP TABLE IF EXISTS scheduled_posts CASCADE")
