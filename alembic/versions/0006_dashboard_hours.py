"""Fresh-observation dashboard aggregates, separate from legacy reporting summaries."""
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE dashboard_station_hours (
            station_id text NOT NULL REFERENCES stations(station_id),
            hour_start timestamptz NOT NULL,
            source_kind text NOT NULL,
            observations integer NOT NULL,
            fresh_observations integer NOT NULL,
            dock_observations integer NOT NULL,
            available_observations integer NOT NULL,
            docks_sum bigint NOT NULL,
            bike_observations integer NOT NULL,
            bikes_sum bigint NOT NULL,
            computed_at timestamptz NOT NULL,
            PRIMARY KEY (station_id, hour_start, source_kind)
        );
        CREATE INDEX ix_dashboard_hours_time ON dashboard_station_hours (hour_start);
        CREATE VIEW reporting.v_dashboard_station_hours AS
            SELECT * FROM dashboard_station_hours;
        DO $grants$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname='bikeshare_api') THEN
            GRANT SELECT ON dashboard_station_hours TO bikeshare_api;
          END IF;
          IF EXISTS (SELECT FROM pg_roles WHERE rolname='bikeshare_ingest') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON dashboard_station_hours TO bikeshare_ingest;
          END IF;
          IF EXISTS (SELECT FROM pg_roles WHERE rolname='bikeshare_reporter') THEN
            GRANT SELECT ON reporting.v_dashboard_station_hours TO bikeshare_reporter;
          END IF;
        END $grants$;
    """)


def downgrade() -> None:
    op.execute('DROP VIEW reporting.v_dashboard_station_hours; DROP TABLE dashboard_station_hours;')
