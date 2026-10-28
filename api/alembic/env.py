from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import DATABASE_URL
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def run_migrations_offline():
    context.configure(url=DATABASE_URL, target_metadata=Base.metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    with create_engine(DATABASE_URL).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
