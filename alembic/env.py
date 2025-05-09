import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# This must be before other imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now app imports are available
from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402, Your SQLAlchemy Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the sqlalchemy.url with our app's DATABASE_URL
config.set_main_option("sqlalchemy.url", settings.effective_database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Run migrations in the current context."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Handle the database URL for async connections
    db_url = settings.effective_database_url

    # Prevent using SQLite in any environment
    if db_url.startswith("sqlite://"):
        raise ValueError(
            "SQLite database is not supported. "
            "Please configure a PostgreSQL database using DATABASE_URL."
        )

    # Ensure postgresql dialect for postgres with asyncpg driver
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        raise ValueError(
            "Unsupported database type. Only PostgreSQL is supported. "
            "Please configure a PostgreSQL database using DATABASE_URL."
        )

    # Create the async engine
    engine = create_async_engine(db_url)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # For async migrations, we need to run in an asyncio loop
    asyncio.run(run_migrations_online())
