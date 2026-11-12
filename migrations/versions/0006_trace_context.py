from alembic import op


revision = "0006"
down_revision = "0005"


def upgrade():
    op.execute("""
    ALTER TABLE outbox ADD COLUMN trace_context jsonb;
    ALTER TABLE outbox ADD CONSTRAINT outbox_trace_context_check CHECK (
        trace_context IS NULL OR (
            jsonb_typeof(trace_context) = 'object'
            AND trace_context ? 'traceparent'
            AND jsonb_typeof(trace_context->'traceparent') = 'string'
            AND length(trace_context->>'traceparent') = 55
            AND (
                NOT (trace_context ? 'tracestate')
                OR (
                    jsonb_typeof(trace_context->'tracestate') = 'string'
                    AND length(trace_context->>'tracestate') <= 512
                )
            )
            AND trace_context - ARRAY['traceparent','tracestate'] = '{}'::jsonb
        )
    );
    CREATE TABLE incident_transitions (
        id bigserial PRIMARY KEY,
        incident_id bigint NOT NULL REFERENCES incidents(id),
        transition text NOT NULL CHECK (transition IN (
            'detected','hold_applied','verification_started','verified',
            'recurrence','escalated','acknowledged','resolved'
        )),
        occurred_at timestamptz NOT NULL DEFAULT now(),
        score double precision
    );
    CREATE INDEX incident_transition_history
        ON incident_transitions(transition, occurred_at);
    """)


def downgrade():
    raise RuntimeError("Restore backup instead of destructive downgrade")
