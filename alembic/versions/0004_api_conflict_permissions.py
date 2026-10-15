"""Allow idempotent recommendation inserts without reading rider coordinates.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $grants$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bikeshare_api') THEN
            GRANT SELECT (id) ON recommendation_requests TO bikeshare_api;
            GRANT SELECT (request_id, policy_id, rank) ON recommendation_results TO bikeshare_api;
          END IF;
        END
        $grants$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $grants$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='bikeshare_api') THEN
            REVOKE SELECT (id) ON recommendation_requests FROM bikeshare_api;
            REVOKE SELECT (request_id, policy_id, rank) ON recommendation_results FROM bikeshare_api;
          END IF;
        END
        $grants$;
    """)
