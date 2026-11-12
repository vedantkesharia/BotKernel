from alembic import op
revision = "0007"
down_revision = "0006"
def upgrade():
    op.execute("""
    CREATE TABLE investigation_reports (
      id uuid PRIMARY KEY, incident_id bigint NOT NULL REFERENCES incidents(id),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 200),
      request_fingerprint text NOT NULL CHECK(length(request_fingerprint)=64),
      status text NOT NULL CHECK(status IN ('RUNNING','COMPLETE','INSUFFICIENT_EVIDENCE','FAILED')),
      provider text NOT NULL CHECK(provider='deterministic_mock'), report jsonb,
      error_category text CHECK(error_category IS NULL OR error_category IN ('execution_error','lease_expired')),
      created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
      lease_token uuid, lease_until timestamptz,
      UNIQUE(incident_id,idempotency_key),
      CHECK(report IS NULL OR (jsonb_typeof(report)='object' AND pg_column_size(report)<=262144)),
      CHECK((status='RUNNING' AND report IS NULL AND completed_at IS NULL AND lease_token IS NOT NULL AND lease_until IS NOT NULL) OR (status IN ('COMPLETE','INSUFFICIENT_EVIDENCE') AND report IS NOT NULL AND completed_at IS NOT NULL AND lease_token IS NULL AND lease_until IS NULL AND error_category IS NULL) OR (status='FAILED' AND report IS NULL AND completed_at IS NOT NULL AND lease_token IS NULL AND lease_until IS NULL AND error_category IS NOT NULL))
    );
    CREATE INDEX investigation_reports_incident_created ON investigation_reports(incident_id,created_at DESC);
    """)
def downgrade():
    raise RuntimeError("Restore backup instead of destructive downgrade")
