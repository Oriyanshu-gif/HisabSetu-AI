"""The deploy-time SQLite path helper.

Hosted platforms hand the app a database path inside a folder that does not
exist yet (``/var/data/khata.db``); SQLite's own error for that is
"unable to open database file" at startup, which is hard to diagnose from a
deploy log.  These tests pin the folder-creation behaviour and make sure
in-memory / non-SQLite URLs are never touched.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text

from database import _ensure_sqlite_directory


def test_creates_missing_parent_folders(tmp_path):
    target = tmp_path / "data" / "nested" / "khata.db"
    url = f"sqlite:///{target.as_posix()}"

    assert _ensure_sqlite_directory(url) == url
    assert target.parent.is_dir()

    engine = create_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("select 1")).scalar() == 1
    engine.dispose()


def test_leaves_an_existing_folder_alone(tmp_path):
    target = tmp_path / "khata.db"
    url = f"sqlite:///{target.as_posix()}"
    assert _ensure_sqlite_directory(url) == url
    assert target.parent.is_dir()


def test_never_touches_in_memory_databases():
    assert _ensure_sqlite_directory("sqlite:///:memory:") == "sqlite:///:memory:"
    assert _ensure_sqlite_directory("sqlite://") == "sqlite://"


def test_ignores_non_sqlite_urls():
    url = "postgresql+psycopg://user:secret@db.example.com:5432/khata"
    assert _ensure_sqlite_directory(url) == url


def test_returns_the_url_even_when_the_folder_cannot_be_created(tmp_path, monkeypatch):
    """A read-only filesystem must not crash import time; SQLite reports it."""
    target = tmp_path / "locked" / "khata.db"
    url = f"sqlite:///{target.as_posix()}"

    def boom(self, *args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr("pathlib.Path.mkdir", boom)
    assert _ensure_sqlite_directory(url) == url
