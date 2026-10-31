"""Run migrations with an explicit PostgreSQL URL and shared model metadata."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401
from app.db.base import Base

config = context.config
target_metadata = Base.metadata


def database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be explicitly configured for migrations")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Migrations require PostgreSQL with the psycopg driver")
    return url


if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
