"""Database engine factory.

Reads DATABASE_URL from the environment (psycopg v3 driver).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    """Create a SQLAlchemy engine from the ``DATABASE_URL`` environment variable.

    Returns:
        A SQLAlchemy ``Engine`` bound to ``DATABASE_URL`` (psycopg v3 driver).

    Raises:
        RuntimeError: If ``DATABASE_URL`` is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return create_engine(url)
