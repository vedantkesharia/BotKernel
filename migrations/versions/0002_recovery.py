from alembic import op
revision = "0002"
down_revision = "0001"

def upgrade():
    op.execute("""
    ALTER TABLE actions DROP CONSTRAINT actions_state_check;
    ALTER TABLE actions ADD CONSTRAINT actions_state_check CHECK(state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','SUCCEEDED','FAILED','ESCALATED'));
    ALTER TABLE actions ADD COLUMN attempts int NOT NULL DEFAULT 0 CHECK(attempts>=0), ADD COLUMN next_attempt timestamptz NOT NULL DEFAULT now(), ADD COLUMN last_error text;
    DROP INDEX resource_reservation;
    CREATE UNIQUE INDEX resource_reservation ON actions(resource) WHERE state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','ESCALATED');
    CREATE TABLE dead_letters(topic text, partition_id int, offset_id bigint, reason text NOT NULL, PRIMARY KEY(topic,partition_id,offset_id));
    CREATE OR REPLACE FUNCTION guard_transition() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF OLD.state <> NEW.state AND NOT (
      (OLD.state='RESERVED' AND NEW.state IN ('DISPATCHED','FAILED','ESCALATED')) OR
      (OLD.state='DISPATCHED' AND NEW.state IN ('SUCCEEDED','OUTCOME_UNKNOWN','FAILED','ESCALATED')) OR
      (OLD.state='OUTCOME_UNKNOWN' AND NEW.state IN ('DISPATCHED','FAILED','ESCALATED')))
    THEN RAISE EXCEPTION 'illegal transition'; END IF;
    RETURN NEW; END $$;
    """)

def downgrade():
    raise RuntimeError("Restore backup instead of destructive downgrade")
