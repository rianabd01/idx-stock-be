from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.core.config import DATABASE_URL


@contextmanager
def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn
