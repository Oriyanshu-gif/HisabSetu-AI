"""Pytest configuration.

The test suite never calls Gnani and never needs an API key:

* ``GNANI_API_KEY`` is forced empty before the app modules are imported.
* A throwaway SQLite file is used, and every test starts from empty tables.
* Sample seeding is disabled so each test controls its own ledger.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP_DIR = Path(tempfile.mkdtemp(prefix="voice_khata_tests_"))
os.environ["VOICE_KHATA_DB_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["VOICE_KHATA_SEED"] = "0"
os.environ["GNANI_API_KEY"] = ""
os.environ["GNANI_BASE_URL"] = "https://api.vachana.ai"
os.environ["GNANI_AUTH_HEADER"] = "X-API-Key-ID"
os.environ["GNANI_AUTH_SCHEME"] = ""
os.environ["GNANI_TTS_MODEL"] = "timbre-v2.5"
os.environ["GNANI_TTS_VOICE"] = "Nalini"
os.environ["MAX_RECORD_SECONDS"] = "30"


@pytest.fixture(autouse=True)
def clean_database():
    """Drop and recreate every table before each test."""
    import models  # noqa: F401
    from database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    from database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as test_client:
        yield test_client


def make_wav(seconds: float = 1.0, rate: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    """Silent PCM WAV with a valid header (used for upload tests)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        frames = int(rate * seconds)
        writer.writeframes(b"\x00" * frames * channels * width)
    return buffer.getvalue()


def make_customer(db, name: str, is_sample: bool = False):
    from models import Customer
    from parser import normalize_name
    from services import utcnow

    customer = Customer(
        name=name,
        name_normalized=normalize_name(name),
        is_sample=is_sample,
        created_at=utcnow(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def post_entry(db, customer, txn_type: str, rupees, transcript: str = "test entry"):
    from services import TYPE_CREDIT, TYPE_PAYMENT, confirm_pending, create_pending

    assert txn_type in {TYPE_CREDIT, TYPE_PAYMENT}
    from money import to_paise

    pending = create_pending(
        db,
        customer=customer,
        txn_type=txn_type,
        amount_paise=to_paise(rupees),
        transcript=transcript,
        source="text",
        parser_info={},
    )
    return confirm_pending(db, pending["pending_id"], acknowledge_overpayment=True)
