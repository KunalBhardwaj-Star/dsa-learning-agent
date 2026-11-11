
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)


def build_database_url():
    """Build a PostgreSQL URL. Never fall back to SQLite."""

    database_url = os.getenv("DATABASE_URL", "").strip()

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url[len("postgres://"):]

        try:
            url = make_url(database_url)
        except Exception as exc:
            raise RuntimeError(
                "DATABASE_URL is invalid. Check your .env configuration."
            ) from exc

        if url.get_backend_name() != "postgresql":
            raise RuntimeError(
                "Only PostgreSQL is supported. SQLite fallback is disabled."
            )

        return url

    username = os.getenv("DB_USERNAME", "postgres").strip()
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "127.0.0.1").strip()
    port = os.getenv("DB_PORT", "5432").strip()
    database = os.getenv("DB_DATABASE", "dsa_learning_agent").strip()

    if not password:
        raise RuntimeError(
            "DB_PASSWORD is missing. Configure it in your .env file."
        )

    try:
        port = int(port)
    except ValueError as exc:
        raise RuntimeError("DB_PORT must be an integer.") from exc

    return URL.create(
        drivername="postgresql+psycopg2",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )


DATABASE_URL = build_database_url()

# Safe to log: the password is hidden.
ACTIVE_DATABASE_URL = DATABASE_URL.render_as_string(
    hide_password=True
)

is_postgres = True

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def verify_database_connection():
    """Raise a clear error if PostgreSQL is unavailable."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    except Exception as exc:
        logger.exception(
            "PostgreSQL connection failed: %s",
            ACTIVE_DATABASE_URL,
        )
        raise RuntimeError(
            f"Cannot connect to PostgreSQL at {ACTIVE_DATABASE_URL}. "
            "Check PostgreSQL service and .env settings."
        ) from exc

    logger.info(
        "Successfully connected to PostgreSQL: %s",
        ACTIVE_DATABASE_URL,
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
