from alembic import op
from pathlib import Path
revision = "0001"
down_revision = None

def upgrade():
    op.get_bind().exec_driver_sql(Path(__file__).with_name("0001_schema.sql").read_text())

def downgrade():
    raise RuntimeError("Destructive downgrade unsupported; restore a database backup")
