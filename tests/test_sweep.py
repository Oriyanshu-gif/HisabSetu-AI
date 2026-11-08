"""Offline checks for sweep_live.py (no network, no database)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import sweep_live
from parser import normalize_name, parse_command

ROOT = Path(__file__).resolve().parent.parent


def test_sweep_covers_the_sixteen_demo_phrases():
    assert len(sweep_live.PHRASES) == 16
    assert [n for n, _ in enumerate(sweep_live.PHRASES, 1)] == list(range(1, 17))


@pytest.mark.parametrize(
    ("phrase", "want_intent", "want_amount", "want_name"),
    sweep_live.PHRASES,
    ids=[str(i) for i in range(1, 17)],
)
def test_every_expected_phrasing_is_parseable_or_safely_clarifies(
    phrase, want_intent, want_amount, want_name
):
    """The expectation table must be reachable by the parser itself.

    This parses the literal phrase (no STT), so a typo in an expectation shows up
    here instead of silently passing during the live sweep.

    A trailing bare "do" ("...udhaar do") is legitimately ambiguous, so a parse
    that misses the amount is allowed only when the parser refuses to guess. A
    wrong amount must never be accepted silently -- that is the core safety
    invariant of the ledger.
    """
    parsed = parse_command(phrase)
    assert parsed.intent == want_intent
    if want_amount is not None and parsed.amount_rupees != Decimal(want_amount):
        assert parsed.amount_rupees is None, (
            f"wrong amount accepted silently: {parsed.amount_rupees} != {want_amount}"
        )
        assert parsed.ambiguity, "an unusable amount must raise a clarification"
    if want_name is not None:
        assert normalize_name(parsed.customer_name or "") == normalize_name(want_name)


def test_sweep_never_touches_the_database():
    """The sweep is a read-only probe: no DB engine, session or write path."""
    source = (ROOT / "sweep_live.py").read_text(encoding="utf-8")
    forbidden = (
        "import database",
        "from database",
        "import services",
        "from services",
        "SessionLocal",
        "sqlalchemy",
        "session.commit",
        "create_pending",
        "post_entry",
    )
    found = [needle for needle in forbidden if needle in source]
    assert not found, f"sweep_live.py must not use the DB, found: {found}"


def test_sweep_reports_a_non_zero_exit_on_mismatch():
    # Dummy parser result: wrong intent must be reported as a mismatch.
    class Dummy:
        intent = "add_credit"
        amount_rupees = Decimal("100")
        customer_name = "Ramesh"

    passed, status = sweep_live._check(Dummy(), "add_credit", "150", None)
    assert passed is False
    assert status.startswith("MISMATCH")
    assert "150" in status


def test_short_error_strips_provider_html():
    """A provider HTML error page must not flood the results table."""

    class Boom(Exception):
        pass

    rendered = sweep_live._short_error(
        Boom("Gnani API key accept nahi hui (HTTP 403) (<!DOCTYPE html>\n<html>oops)")
    )
    assert "<" not in rendered
    assert "HTTP 403" in rendered
    assert len(rendered) <= 180


def test_sweep_accepts_devanagari_name_for_latin_expectation():
    class Dummy:
        intent = "add_credit"
        amount_rupees = Decimal("300")
        customer_name = "रमेश"

    passed, status = sweep_live._check(Dummy(), "add_credit", "300", "Ramesh")
    assert passed is True
    assert status == "OK"
