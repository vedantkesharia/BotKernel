from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.execute("""
    ALTER TABLE incidents
        ADD COLUMN intervention_count int NOT NULL DEFAULT 1 CHECK(intervention_count >= 0),
        ADD COLUMN recurrence_count int NOT NULL DEFAULT 0 CHECK(recurrence_count >= 0),
        ADD COLUMN verification_started_at timestamptz,
        ADD COLUMN monitor_started_at timestamptz NOT NULL DEFAULT now(),
        ADD COLUMN healthy_samples int NOT NULL DEFAULT 0 CHECK(healthy_samples >= 0),
        ADD COLUMN last_score double precision,
        ADD COLUMN last_observed_at timestamptz,
        ADD COLUMN escalated_at timestamptz,
        ADD COLUMN reopened_at timestamptz;
    ALTER TABLE incidents
        ADD CONSTRAINT incidents_status_check
        CHECK(status IN ('HOLD','VERIFYING','VERIFIED','ESCALATED'));
    CREATE INDEX incident_lifecycle_lookup ON incidents(resource, opened_at DESC);
    """)


def downgrade():
    raise RuntimeError("Restore backup instead of destructive downgrade")
