"""Apply least-privilege grants when application roles exist.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        REVOKE CREATE ON SCHEMA public FROM PUBLIC;

        DO $grants$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_ingest') THEN
            GRANT USAGE ON SCHEMA public TO bikeshare_ingest;
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public
              TO bikeshare_ingest;
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bikeshare_ingest;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
              GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bikeshare_ingest;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
              GRANT USAGE, SELECT ON SEQUENCES TO bikeshare_ingest;
          END IF;

          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_api') THEN
            GRANT USAGE ON SCHEMA public TO bikeshare_api;
            GRANT SELECT ON source_datasets, poll_batches, stations,
              station_metadata_versions, station_snapshots, serving_feature_rows,
              model_runs TO bikeshare_api;
            GRANT INSERT ON recommendation_requests, recommendation_results TO bikeshare_api;
          END IF;

          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_reporter') THEN
            GRANT USAGE ON SCHEMA reporting TO bikeshare_reporter;
            GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO bikeshare_reporter;
            ALTER ROLE bikeshare_reporter SET statement_timeout = '30s';
            ALTER DEFAULT PRIVILEGES IN SCHEMA reporting
              GRANT SELECT ON TABLES TO bikeshare_reporter;
          END IF;
        END
        $grants$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $revoke$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_ingest') THEN
            REVOKE ALL ON ALL TABLES IN SCHEMA public FROM bikeshare_ingest;
            REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM bikeshare_ingest;
            REVOKE USAGE ON SCHEMA public FROM bikeshare_ingest;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_api') THEN
            REVOKE ALL ON ALL TABLES IN SCHEMA public FROM bikeshare_api;
            REVOKE USAGE ON SCHEMA public FROM bikeshare_api;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bikeshare_reporter') THEN
            REVOKE ALL ON ALL TABLES IN SCHEMA reporting FROM bikeshare_reporter;
            REVOKE USAGE ON SCHEMA reporting FROM bikeshare_reporter;
          END IF;
        END
        $revoke$;
        """
    )
