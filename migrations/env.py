from alembic import context
from alembic.script import ScriptDirectory
from botkernel.core import engine
from botkernel.schema_validation import validate_schema
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        if context.get_context().get_current_revision() is None:
            validate_schema(connection, legacy=True)
        context.run_migrations()
        if context.get_context().get_current_revision() == ScriptDirectory.from_config(context.config).get_current_head():
            validate_schema(connection, legacy=False)
