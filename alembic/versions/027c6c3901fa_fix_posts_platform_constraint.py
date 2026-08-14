from alembic import op


revision = "027c6c3901fa"
down_revision = "21363594d293"


def upgrade():
    op.drop_constraint(
        "posts_platform_check",
        "posts",
        type_="check"
    )

    op.create_check_constraint(
        "posts_platform_check",
        "posts",
        "platform IN ('instagram', 'facebook')"
    )


def downgrade():
    op.drop_constraint(
        "posts_platform_check",
        "posts",
        type_="check"
    )

    op.create_check_constraint(
        "posts_platform_check",
        "posts",
        "platform IN ('Instagram', 'Facebook')"
    )