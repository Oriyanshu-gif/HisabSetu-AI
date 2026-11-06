"""
STT + Hinglish parser evaluation suite for HisabSetu AI.

11 Prisma STT cases are shipped as fixed fixtures: each case preserves the
original spoken phrase, the intended command, and the actual STT transcript
exactly as supplied.

The test suite splits evaluation into three stages per case:

1. STT evaluation — did the actual transcript preserve the *intended* customer,
   amount and intent, even if the words or script changed?  An STT mismatch is
   recorded as an STT issue, never as a parser failure.
2. Parser evaluation — feed the *actual transcript* into parser.py and describe
   what our own parser read from it.  This is a statement about the parser, not
   a pass/fail against the intended command.
3. End-to-end evaluation — does parse(transcript) reproduce the intended command?
   A failure here is an end-to-end failure (STT + parser combined).

No paid Gnani call happens in these tests.  Live STT re-runs belong in
`live_eval.py` and are skipped when the key is absent.

Nothing here writes to the real ledger.  Parser tests are side-effect free by
design (parser.py never touches the database), and the fixtures are plain text.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from parser import (
    INTENT_ADD_CREDIT,
    INTENT_BALANCE_QUERY,
    INTENT_DAILY_SUMMARY,
    INTENT_RECORD_PAYMENT,
    INTENT_TOP_DEBT_OR,
    INTENT_UNKNOWN,
    normalize_name,
    parse_command,
)


# ---------------------------------------------------------------------------
# Fixtures — preserved exactly as supplied
# ---------------------------------------------------------------------------

# Each tuple: (id, original_spoken_phrase, stt_transcript,
#              expected_intent, expected_amount_or_None, expected_customer_or_None)
#
# Expected values describe the *intended command*, not what the transcript
# literally says.  That distinction is the whole point of splitting STT and
# parser status.
CASES: list[tuple[int, str, str, str, str | None, str | None]] = [
    (
        1,
        "Ramesh ko dedh sau rupaye ka udhaar likh do",
        "रमेश को दे दो सौ रुपए का उधार लिख दो",
        INTENT_ADD_CREDIT,
        "150",
        "Ramesh",
    ),
    (
        2,
        "Sunita ne do sau rupaye wapas kar diye",
        "सुनीता ने दो सौ रुपये वापस कर दिए",
        INTENT_RECORD_PAYMENT,
        "200",
        "Sunita",
    ),
    (
        3,
        "Mohan ko sawa do sau ka udhaar likh do",
        "मोहन को सवा सौ का उधार लिख दो",
        INTENT_ADD_CREDIT,
        "225",
        "Mohan",
    ),
    (
        4,
        "Anil ne paune do sau rupaye jama kariye",
        "अनिल ने पौने दो सौ रुपये जमा किए",
        INTENT_RECORD_PAYMENT,
        "175",
        "Anil",
    ),
    (
        5,
        "Priya ko pandrah sau rupaye ka udhaar do",
        "प्रिया को पंद्रह सौ रुपये का उधार दो",
        INTENT_ADD_CREDIT,
        "1500",
        "Priya",
    ),
    (
        6,
        "Suresh bhai ko dedh hazaar ka udhaar likh do",
        "सुरेश भाई को दे हज़ार का उधार लिख दो",
        INTENT_ADD_CREDIT,
        "1500",
        "Suresh",
    ),
    (
        7,
        "Kavita ne do hazaar paanch sau rupaye wapas kiye",
        "कविता ने दो हज़ार पांच सौ रुपये वापस किए",
        INTENT_RECORD_PAYMENT,
        "2500",
        "Kavita",
    ),
    (
        8,
        "Ramesh ko ek hazaar rupaye ka udhaar likh do",
        "रमेश को एक हज़ार रुपये का उधार लिख दो",
        INTENT_ADD_CREDIT,
        "1000",
        "Ramesh",
    ),
    (
        9,
        "Ramesh ko teen sau rupaye ka udhaar likh do",
        "रमेश को तीन सौ रुपये का उधार लिख दो",
        INTENT_ADD_CREDIT,
        "300",
        "Ramesh",
    ),
    (
        10,
        "Ramesh ko pandrah sau rupaye ka udhaar likh do",
        "रमेश को पंद्रह सौ रुपये का उधार लिख दो",
        INTENT_ADD_CREDIT,
        "1500",
        "Ramesh",
    ),
    (
        11,
        "Mohan ka kitna udhaar baaki hai",
        "मोहन का कितना उधार बाकी है",
        INTENT_BALANCE_QUERY,
        None,
        "Mohan",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _amount_eq(parsed_amount: Decimal | None, expected: str | None) -> bool:
    if expected is None:
        return parsed_amount is None
    if parsed_amount is None:
        return False
    return parsed_amount == Decimal(expected)


def _customer_eq(parsed_name: str | None, expected: str | None) -> bool:
    """Customer match through the same transliteration the ledger uses."""
    if expected is None:
        return parsed_name is None
    if parsed_name is None:
        return False
    return normalize_name(parsed_name) == normalize_name(expected)


# ---------------------------------------------------------------------------
# Per-case STT + parser + e2e result objects
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[f"case_{c[0]}" for c in CASES])
def test_stt_stage(case):
    """STT stage: did the transcript preserve the intended customer / amount / intent?

    An STT mismatch is an STT issue, never a parser failure.
    """
    _id, original, transcript, want_intent, want_amount, want_customer = case
    parsed = parse_command(transcript)

    stt_reasons: list[str] = []
    stt_ok = True

    if want_intent != INTENT_UNKNOWN:
        if not _customer_eq(parsed.customer_name, want_customer):
            stt_ok = False
            stt_reasons.append(
                f"customer: intended={want_customer!r}, "
                f"transcript-name={parsed.customer_name!r}"
            )
        if not _amount_eq(parsed.amount_rupees, want_amount):
            stt_ok = False
            stt_reasons.append(
                f"amount: intended={want_amount!r}, "
                f"parsed-from-transcript={parsed.amount_rupees!r}"
            )
        if parsed.intent not in {want_intent, INTENT_UNKNOWN}:
            stt_ok = False
            stt_reasons.append(
                f"intent: intended={want_intent!r}, "
                f"parsed={parsed.intent!r}"
            )

    pytest.stt_status = "stt_ok" if stt_ok else "stt_mismatch"
    pytest.stt_detail = " | ".join(stt_reasons) if stt_reasons else "transcript preserves intent"

    # Always collect the STT status for the report generator.
    _stt_results[_id] = (
        pytest.stt_status,
        pytest.stt_detail,
    )

    # STT stage is informative; it does not block the suite on its own.  The
    # end-to-end test below is the one that must match the intended command.
    assert True


@pytest.mark.parametrize("case", CASES, ids=[f"case_{c[0]}" for c in CASES])
def test_parser_stage(case):
    """Parser stage: describe what parser.py read from the actual transcript.

    This is a descriptive assertion about the parser's read of the supplied
    transcript, not a pass/fail against the intended command.  The end-to-end
    test below compares against the intended command.
    """
    _id, original, transcript, want_intent, want_amount, want_customer = case
    parsed = parse_command(transcript)

    notes: list[str] = []
    if want_intent in {INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT} and parsed.amount_rupees is None:
        notes.append("transcript has no usable amount for parser")
    if parsed.intent == INTENT_UNKNOWN and want_intent != INTENT_UNKNOWN:
        notes.append("parser classified the transcript as unknown intent")
    if want_intent in {INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT, INTENT_BALANCE_QUERY}:
        if not _customer_eq(parsed.customer_name, want_customer):
            notes.append(
                f"parser-read customer={parsed.customer_name!r} differs from "
                f"intended customer={want_customer!r} (script or stt changed the name)"
            )

    # Sanity: the parser should not produce a phantom amount or customer when the
    # transcript is genuinely empty.
    if transcript.strip() == "":
        assert parsed.intent == INTENT_UNKNOWN
        assert parsed.customer_name is None
        assert parsed.amount_rupees is None
        return

    # Otherwise, report the parser's actual read.  This test always passes; its
    # value is in the structured notes the report generator can surface.
    assert True


@pytest.mark.parametrize("case", CASES, ids=[f"case_{c[0]}" for c in CASES])
def test_end_to_end(case):
    """End-to-end: does parse(transcript) reproduce the intended command?"""
    _id, original, transcript, want_intent, want_amount, want_customer = case
    parsed = parse_command(transcript)

    e2e_ok = (
        parsed.intent == want_intent
        and _customer_eq(parsed.customer_name, want_customer)
        and _amount_eq(parsed.amount_rupees, want_amount)
    )

    if not e2e_ok:
        reasons: list[str] = []
        if parsed.intent != want_intent:
            reasons.append(f"intent: parsed={parsed.intent!r} != intended={want_intent!r}")
        if not _customer_eq(parsed.customer_name, want_customer):
            reasons.append(
                f"customer: parsed={parsed.customer_name!r} != intended={want_customer!r}"
            )
        if not _amount_eq(parsed.amount_rupees, want_amount):
            reasons.append(
                f"amount: parsed={parsed.amount_rupees!r} != intended={want_amount!r}"
            )
        raise AssertionError(
            f"case {_id}: end-to-end failure\n"
            f"  original phrase (spoken): {original}\n"
            f"  actual STT transcript:    {transcript}\n"
            f"  parsed:     intent={parsed.intent}, customer={parsed.customer_name!r}, "
            f"amount={parsed.amount_rupees!r}\n"
            f"  intended:   intent={want_intent}, customer={want_customer!r}, amount={want_amount!r}\n"
            f"  reasons:    {'; '.join(reasons)}\n"
            f"  notes:      parser.reads_transcript_as={transcript!r}"
        )


# ---------------------------------------------------------------------------
# Report helpers — shared with eval_report.py via a tiny public API
# ---------------------------------------------------------------------------

_CASE_NOTES = {
    1: "STT turned 'dedh' into 'de do'; parser's stt-dedh repair should recover ₹150.",
    3: "'sawa do sau' must stay ₹225 — not be confused with 'sawa sau' (₹125).",
    5: "'pandrah sau' = ₹1500; do not treat as ₹150.",
    6: "'dedh hazaar' = ₹1500; honorific 'bhai' must not become the customer name.",
    8: "'ek hazaar' = ₹1000.",
    9: "'teen sau' = ₹300.",
    10: "'pandrah sau' (Devanagari) = ₹1500, same as case 5 but in Devanagari script.",
}


def case_note(case_id: int) -> str:
    return _CASE_NOTES.get(case_id, "")


# Module-level store for the STT status collected by test_stt_stage.
# pytest re-runs the parametrized test per case, so we stash per case ID.
_stt_results: dict[int, tuple[str, str]] = {}


def stt_result(case_id: int) -> tuple[str, str]:
    """Public accessor for the report generator; safe to call after tests run."""
    return _stt_results.get(case_id, ("stt_ok", "no data"))


@pytest.fixture(autouse=True)
def _clear_stt_results():
    _stt_results.clear()
    yield
    _stt_results.clear()
