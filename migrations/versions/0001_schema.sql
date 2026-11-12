CREATE TABLE IF NOT EXISTS agents(id text PRIMARY KEY, heartbeat timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS quota(id int PRIMARY KEY CHECK(id=1),capacity int NOT NULL CHECK(capacity>0));
INSERT INTO quota VALUES(1,20) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS resources(id text PRIMARY KEY,capacity int NOT NULL CHECK(capacity BETWEEN 1 AND 20),version int NOT NULL DEFAULT 0);
INSERT INTO resources VALUES('service-a',4,0),('service-b',4,0) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS external_resources(id text PRIMARY KEY,capacity int NOT NULL);
INSERT INTO external_resources SELECT id,capacity FROM resources ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS actions(id uuid PRIMARY KEY,idempotency_key text UNIQUE NOT NULL,agent text NOT NULL REFERENCES agents(id),resource text NOT NULL REFERENCES resources(id),payload jsonb NOT NULL,delta int NOT NULL,state text NOT NULL CHECK(state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN','SUCCEEDED')),created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX IF NOT EXISTS resource_reservation ON actions(resource) WHERE state IN ('RESERVED','DISPATCHED','OUTCOME_UNKNOWN');
CREATE TABLE IF NOT EXISTS outbox(id bigserial PRIMARY KEY,action_id uuid NOT NULL REFERENCES actions(id),published bool NOT NULL DEFAULT false);
CREATE TABLE IF NOT EXISTS receipts(action_id uuid PRIMARY KEY REFERENCES actions(id));
CREATE OR REPLACE FUNCTION guard_transition() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF OLD.state <> NEW.state AND NOT ((OLD.state='RESERVED' AND NEW.state='DISPATCHED') OR (OLD.state='DISPATCHED' AND NEW.state IN ('SUCCEEDED','OUTCOME_UNKNOWN')) OR (OLD.state='OUTCOME_UNKNOWN' AND NEW.state='DISPATCHED')) THEN RAISE EXCEPTION 'illegal transition'; END IF;
RETURN NEW; END $$;
DROP TRIGGER IF EXISTS action_transition ON actions;
CREATE TRIGGER action_transition BEFORE UPDATE ON actions FOR EACH ROW EXECUTE FUNCTION guard_transition();
