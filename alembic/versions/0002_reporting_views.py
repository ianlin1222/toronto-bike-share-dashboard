"""Install bounded read-only reporting views.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-07
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    source = Path(__file__).parents[2] / "sql" / "reporting" / "001_views.sql"
    sql = source.read_text(encoding="utf-8")
    sql = sql.removeprefix("BEGIN;").removesuffix("COMMIT;\n")
    op.execute(sql)


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS reporting.v_refresh_status;
        DROP VIEW IF EXISTS reporting.v_ingestion_health;
        DROP VIEW IF EXISTS reporting.v_model_calibration;
        DROP VIEW IF EXISTS reporting.v_recommendation_performance;
        DROP VIEW IF EXISTS reporting.v_station_hourly_availability;
        DROP VIEW IF EXISTS reporting.v_station_current;
        """
    )
