from alembic import op
revision="0003"
down_revision="0002"
def upgrade():
    op.execute("""
    CREATE TABLE effects(action_id uuid PRIMARY KEY REFERENCES actions(id),resource text NOT NULL,agent text NOT NULL,version int NOT NULL,before_capacity int NOT NULL,after_capacity int NOT NULL,latency double precision NOT NULL,observed_at timestamptz NOT NULL DEFAULT now(),UNIQUE(resource,version));
    CREATE INDEX effect_window ON effects(resource,observed_at);
    CREATE TABLE incidents(id bigserial PRIMARY KEY,resource text NOT NULL,score double precision NOT NULL,evidence jsonb NOT NULL,status text NOT NULL DEFAULT 'HOLD',opened_at timestamptz NOT NULL DEFAULT now(),hold_until timestamptz NOT NULL DEFAULT now()+interval '20 seconds',verified_at timestamptz);
    CREATE UNIQUE INDEX one_incident ON incidents(resource) WHERE status='HOLD';
    """)
def downgrade():
    raise RuntimeError("Restore backup")
