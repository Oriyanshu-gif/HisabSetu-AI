"""Database engine, session factory and helpers.

The app uses SQLite for a zero-setup local install. All timestamps are stored as
naive UTC datetimes; the UI converts them to Asia/Kolkata (IST).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings


def _ensure_sqlite_directory(url: str) -> str:
    """Create the parent folder of a file-backed SQLite database.

    Hosted platforms hand you a path such as ``/var/data/khata.db`` whose folder
    does not exist yet; SQLite then fails at startup with the unhelpful
    "unable to open database file".  Creating the folder here keeps the deploy
    step to a single environment variable.  A read-only filesystem is left
    alone — the driver error is clearer than anything we could raise.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix):]
    if not path or path in {":memory:", ""} or path.startswith(":memory:"):
        return url
    try:
        parent = Path(path).expanduser().parent
        if parent and not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover - read-only filesystem / permissions
        pass
    return url


settings_db_url = _ensure_sqlite_directory(settings.database_url)
_is_sqlite = settings_db_url.startswith("sqlite")

engine = create_engine(
    settings_db_url,
    connect_args={"check_same_thread": False, "timeout": 15} if _is_sqlite else {},
    future=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
