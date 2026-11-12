from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    op.execute("""
    ALTER TABLE incidents
        DROP CONSTRAINT incidents_status_check,
        ADD COLUMN resolved_at timestamptz,
        ADD CONSTRAINT incidents_status_check
            CHECK(status IN ('HOLD','VERIFYING','VERIFIED','ESCALATED','RESOLVED'));
    CREATE TABLE incident_operator_actions (
        id bigserial PRIMARY KEY,
        incident_id bigint NOT NULL REFERENCES incidents(id),
        action text NOT NULL CHECK(action IN ('ACKNOWLEDGE','RESOLVE')),
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 200),
        reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 500),
        actor text NOT NULL DEFAULT 'local-console',
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(incident_id,idempotency_key)
    );
    CREATE INDEX incident_operator_action_history
        ON incident_operator_actions(incident_id,created_at,id);
    """)


def downgrade():
    raise RuntimeError("Restore backup instead of destructive downgrade")
