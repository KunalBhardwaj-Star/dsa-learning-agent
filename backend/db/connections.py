import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


class PgConnectionWrapper:
    """Wrapper around psycopg2 connection to support MySQL-style cursor(dictionary=True)."""

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self, dictionary: bool = False, **kwargs):
        if dictionary:
            return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor, **kwargs)
        return self._conn.cursor(**kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_connection():
    raw_conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USERNAME", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_DATABASE", "dsa_learning_agent"),
    )
    return PgConnectionWrapper(raw_conn)