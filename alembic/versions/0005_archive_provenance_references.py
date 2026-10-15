"""Retain snapshot identifiers after verified snapshots move into archives.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      DO $archive_refs$
      DECLARE item record;
      BEGIN
        FOR item IN
          SELECT conrelid::regclass AS relation, conname FROM pg_constraint
          WHERE contype='f' AND confrelid='station_snapshots'::regclass
            AND conrelid IN ('recommendation_results'::regclass, 'evaluation_outcomes'::regclass)
        LOOP
          EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', item.relation, item.conname);
        END LOOP;
      END
      $archive_refs$;
    """)


def downgrade() -> None:
    op.execute("""
      ALTER TABLE recommendation_results ADD CONSTRAINT fk_recommendation_snapshot
        FOREIGN KEY (snapshot_id, snapshot_retrieved_at)
        REFERENCES station_snapshots(snapshot_id, retrieved_at) NOT VALID;
      ALTER TABLE evaluation_outcomes ADD CONSTRAINT fk_outcome_snapshot
        FOREIGN KEY (matched_snapshot_id, matched_snapshot_retrieved_at)
        REFERENCES station_snapshots(snapshot_id, retrieved_at) NOT VALID;
    """)
