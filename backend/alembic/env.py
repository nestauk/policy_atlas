"""Alembic env — target metadata from schema.py; reads DATABASE_URL from environment."""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import engine_from_config, pool

from policy_atlas.core.schema import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _get_url() -> str:
    # Explicit environment first; fall back to backend/.env WITHOUT mutating
    # os.environ — a blanket load_dotenv() here re-injected a developer's live
    # keys into the pytest process every time a fixture ran a migration,
    # flipping key-switched code paths live under socket-deny (task 025
    # live-check finding). dotenv_values() reads the file side-effect-free.
    url = os.environ.get("DATABASE_URL") or dotenv_values().get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
