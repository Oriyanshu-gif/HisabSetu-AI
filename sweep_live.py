"""Live phrase sweep against the real Gnani API.

For every phrase: Timbre TTS -> Prisma STT -> our parser, and compare the parse
with what a shopkeeper meant. This is a *read-only* probe: it never imports the
database, creates a customer, or writes a transaction.

Usage:
    python sweep_live.py              # all phrases
    python sweep_live.py --only 1,4   # a subset (1-based, original numbering kept)
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from decimal import Decimal

from audio_utils import prepare_for_stt
from gnani_client import is_configured, synthesize, transcribe
from parser import (
    INTENT_ADD_CREDIT,
    INTENT_BALANCE_QUERY,
    INTENT_DAILY_SUMMARY,
    INTENT_RECORD_PAYMENT,
    INTENT_TOP_DEBTOR,
    normalize_name,
    parse_command,
)

# (phrase, expected intent, expected amount or None, expected name or None)
PHRASES: list[tuple[str, str, str | None, str | None]] = [
    ("Ramesh ko dedh sau rupaye ka udhaar likh do", INTENT_ADD_CREDIT, "150", None),
    ("Ramesh ko dhai sau rupaye ka udhaar likh do", INTENT_ADD_CREDIT, "250", None),
    ("Sunita ne do sau rupaye wapas kar diye", INTENT_RECORD_PAYMENT, "200", None),
    ("Mohan ko sawa do sau ka udhaar likh do", INTENT_ADD_CREDIT, "225", None),
    ("Anil ne paune do sau rupaye jama kiye", INTENT_RECORD_PAYMENT, "175", None),
    ("Priya ko paanch sau rupaye udhaar do", INTENT_ADD_CREDIT, "500", None),
    ("Suresh ko dedh hazaar rupaye ka udhaar likh do", INTENT_ADD_CREDIT, "1500", None),
    ("Kavita ne do hazaar paanch sau rupaye wapas kar diye", INTENT_RECORD_PAYMENT, "2500", None),
    ("Ramesh ko ek hazaar rupaye ka udhaar likh do", INTENT_ADD_CREDIT, "1000", None),
    ("Ramesh bhai ko teen sau ka udhaar likh do", INTENT_ADD_CREDIT, "300", "Ramesh"),
    ("Ramesh ko saade teen sau ka udhaar likh do", INTENT_ADD_CREDIT, "350", None),
    ("Sunita ne paanch sau rupaye jama kiye", INTENT_RECORD_PAYMENT, "500", None),
    ("Ramesh ko pandrah sau rupaye ka udhaar likh do", INTENT_ADD_CREDIT, "1500", None),
    ("Mohan ka kitna udhaar baaki hai", INTENT_BALANCE_QUERY, None, None),
    ("Sabse zyada udhaar kis customer ka hai", INTENT_TOP_DEBTOR, None, None),
    ("Aaj ka poora hisaab batao", INTENT_DAILY_SUMMARY, None, None),
]

HEADERS = ("#", "Phrase", "Prisma transcript", "intent / amount / name", "vs expected")


def _width(text: str) -> int:
    """Approximate display width; Devanagari combining marks take no cell."""
    total = 0
    for char in text:
        if unicodedata.combining(char) or char in {"\u094d", "\u200d", "\ufe0f"}:
            continue
        total += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return total


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - _width(text), 0)


def _short_error(exc: Exception) -> str:
    """One readable line; provider HTML error pages must not flood the table."""
    text = " ".join(str(exc).split())
    if "<" in text:
        text = text.split("<")[0].rstrip(" :-(")
    if len(text) > 140:
        text = text[:137] + "..."
    return f"{type(exc).__name__}: {text}"


def _check(parsed, want_intent: str, want_amount: str | None,
           want_name: str | None) -> tuple[bool, str]:
    problems: list[str] = []
    if parsed.intent != want_intent:
        problems.append(f"intent {parsed.intent} != {want_intent}")
    if want_amount is not None:
        if parsed.amount_rupees is None:
            problems.append(f"amount None != {want_amount}")
        elif parsed.amount_rupees != Decimal(want_amount):
            problems.append(f"amount {parsed.amount_rupees} != {want_amount}")
    # Prisma returns Devanagari (रमेश) even for a Latin phrase, so compare names
    # the way the ledger does: through normalize_name transliteration.
    if want_name is not None and normalize_name(parsed.customer_name or "") != normalize_name(want_name):
        problems.append(f"name {parsed.customer_name!r} != {want_name!r}")
    if problems:
        return False, "MISMATCH: " + "; ".join(problems)
    return True, "OK"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Gnani phrase sweep (read-only)")
    parser.add_argument("--only", help="comma separated 1-based phrase numbers")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not is_configured():
        print("SKIPPED: GNANI_API_KEY is not configured (.env).")
        return 2

    numbered = list(enumerate(PHRASES, 1))
    if args.only:
        wanted = {int(part) for part in args.only.split(",") if part.strip()}
        numbered = [(n, p) for n, p in numbered if n in wanted]

    table: list[list[str]] = []
    ok_count = 0

    for number, (phrase, want_intent, want_amount, want_name) in numbered:
        try:
            audio = synthesize(phrase).audio
            prepared = prepare_for_stt(audio, filename="sweep.wav")
            transcript = transcribe(prepared.data).transcript
            parsed = parse_command(transcript)
            passed, status = _check(parsed, want_intent, want_amount, want_name)
            parsed_text = (
                f"{parsed.intent} / "
                f"{parsed.amount_rupees if parsed.amount_rupees is not None else '-'} / "
                f"{parsed.customer_name or '-'}"
            )
            if passed:
                ok_count += 1
        except Exception as exc:  # noqa: BLE001 - isolate one bad phrase, print why
            transcript = "-"
            parsed_text = "-"
            status = f"ERROR: {_short_error(exc)}"

        table.append([str(number), phrase, transcript, parsed_text, status])

    widths = [
        max([_width(h)] + [_width(row[i]) for row in table])
        for i, h in enumerate(HEADERS)
    ]
    print(" | ".join(_pad(HEADERS[i], widths[i]) for i in range(len(HEADERS))))
    print("-+-".join("-" * widths[i] for i in range(len(HEADERS))))
    for row in table:
        print(" | ".join(_pad(row[i], widths[i]) for i in range(len(HEADERS))))

    total = len(table)
    print()
    print(f"SUMMARY: {ok_count}/{total} OK, {total - ok_count} mismatch/error")
    return 0 if ok_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
