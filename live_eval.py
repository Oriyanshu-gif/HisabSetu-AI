"""
Live Gnani STT re-run for the same 21 evaluation cases (11 quiet, 10 noisy).

This is a *separate* script from the unit tests and the report generator.
It is only useful when you have a configured Gnani key and want to re-verify
the same 21 cases against real audio through TTS -> STT -> parser.

It never writes to the ledger, never creates customers, and never commits a
transaction.  It transcribes and parses only.

Usage:
    python live_eval.py              # all 21 cases, exits 1 on any mismatch
    python live_eval.py --only 1,14,21  # subset by 1-based test ID
    python live_eval.py --markdown live_report.md

When GNANI_API_KEY is absent or the provider is unreachable, the script prints
a short explanation and exits 2 (so CI can tell "skipped" from "failed").
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
    INTENT_UNKNOWN,
    canonical_name,
    parse_command,
)

from tests.test_stt_parser_evals import (
    CASES,
    SttJudgement,
    _STT_JUDGEMENT_NOTES,
    case_note,
    evaluate_stt_judgement,
    stt_judgement_note,
)

HEADERS = [
    "ID",
    "Condition",
    "Original phrase",
    "TTS -> live STT transcript",
    "Parsed intent / amount / customer",
    "STT judgement",
    "e2e status",
    "Status",
]


def _width(text: str) -> int:
    total = 0
    for char in text:
        if unicodedata.combining(char) or char in {"\u094d", "\u200d", "\ufe0f"}:
            continue
        total += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return total


def _pad(text: str, width: int) -> int:
    return text + " " * max(width - _width(text), 0)


def _short_error(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    if "<" in text:
        text = text.split("<")[0].rstrip(" :-(")
    if len(text) > 140:
        text = text[:137] + "..."
    return f"{type(exc).__name__}: {text}"


def _amount_eq(parsed: Decimal | None, expected: str | None) -> bool:
    if expected is None:
        return parsed is None
    if parsed is None:
        return False
    return parsed == Decimal(expected)


def _customer_eq(parsed: str | None, expected: str | None) -> bool:
    """Script-agnostic customer comparison — the ledger's own key."""
    if expected is None:
        return parsed is None
    if parsed is None:
        return False
    return canonical_name(parsed) == canonical_name(expected)


def evaluate_live(case: tuple[int, str, str, str, str, str | None, str | None]) -> dict:
    cid, _condition, original, _fixture_transcript, want_intent, want_amount, want_customer = case

    row: dict = {
        "id": cid,
        "condition": _condition,
        "original": original,
        "transcript": "—",
        "parsed_intent": "—",
        "parsed_amount": "—",
        "parsed_customer": "—",
        "stt_status": "SKIP",
        "e2e_status": "SKIP",
        "status": "SKIP",
        "detail": "",
    }

    try:
        audio = synthesize(original).audio
        prepared = prepare_for_stt(audio, filename=f"live_eval_case_{cid}.wav")
        stt = transcribe(prepared.data)
        parsed = parse_command(stt.transcript)
    except Exception as exc:  # noqa: BLE001
        row["status"] = "ERROR"
        row["detail"] = _short_error(exc)
        return row

    row["transcript"] = stt.transcript
    row["parsed_intent"] = parsed.intent
    row["parsed_amount"] = (
        str(parsed.amount_rupees) if parsed.amount_rupees is not None else "—"
    )
    row["parsed_customer"] = parsed.customer_name or "—"

    judgement = evaluate_stt_judgement(case)

    stt_ok = (
        judgement.customer_preserved and judgement.amount_preserved
        and judgement.intent_preserved
    )
    row["stt_status"] = "stt_ok" if stt_ok else "stt_mismatch"
    row["stt_detail"] = judgement.reason

    e2e_ok = (
        parsed.intent == want_intent
        and _customer_eq(parsed.customer_name, want_customer)
        and _amount_eq(parsed.amount_rupees, want_amount)
    )
    row["e2e_status"] = "e2e_ok" if e2e_ok else "e2e_fail"

    reasons: list[str] = []
    if parsed.intent != want_intent:
        reasons.append(f"intent {parsed.intent!r} != {want_intent!r}")
    if not _customer_eq(parsed.customer_name, want_customer):
        reasons.append(f"customer {parsed.customer_name!r} != {want_customer!r}")
    if not _amount_eq(parsed.amount_rupees, want_amount):
        reasons.append(f"amount {parsed.amount_rupees!r} != {want_amount!r}")

    if not reasons:
        row["status"] = "OK"
        row["detail"] = "matched intended command"
    else:
        row["status"] = "MISMATCH"
        row["detail"] = "; ".join(reasons)

    return row


def format_table(rows: list[dict]) -> str:
    widths = [
        max([_width(h)] + [_width(str(r[k])) for r in rows])
        for h, k in zip(
            HEADERS,
            ["id", "condition", "original", "transcript", "parsed_intent",
             "stt_status", "e2e_status", "status"],
        )
    ]

    lines: list[str] = []
    lines.append(" | ".join(
        _pad(HEADERS[i], widths[i]) for i in range(len(HEADERS))
    ))
    lines.append("-+-".join("-" * widths[i] for i in range(len(HEADERS))))
    for r in rows:
        parsed = (
            f"{r['parsed_intent']} / {r['parsed_amount']} / "
            f"{r['parsed_customer']}"
        )
        stt_j = r.get("stt_detail", "")
        lines.append(
            " | ".join([
                _pad(str(r["id"]), widths[0]),
                _pad(r["condition"], widths[1]),
                _pad(r["original"], widths[2]),
                _pad(r["transcript"], widths[3]),
                _pad(parsed, widths[4]),
                _pad(r["stt_status"], widths[5]),
                _pad(r["e2e_status"], widths[6]),
                _pad(r["status"], widths[7]),
            ])
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Live Gnani STT eval for the 21 fixture phrases (TTS -> STT round trip)"
    )
    ap.add_argument("--only", help="comma-separated 1-based case IDs")
    ap.add_argument("--markdown", metavar="PATH",
                    help="also write a Markdown table")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not is_configured():
        print("SKIPPED: GNANI_API_KEY is not configured.  "
              "Set it in .env and re-run for a live sweep.")
        return 2

    wanted: set[int] | None = None
    if args.only:
        wanted = {
            int(part) for part in args.only.split(",") if part.strip()
        }

    numbered = [c for c in CASES if wanted is None or c[0] in wanted]
    if not numbered:
        print("SKIPPED: no matching cases for --only.", file=sys.stderr)
        return 2

    rows = [evaluate_live(c) for c in numbered]

    print(format_table(rows))
    quiet_ok = sum(1 for r in rows if r["condition"] == "Shaant" and r["status"] == "OK")
    noisy_ok = sum(1 for r in rows if r["condition"] == "Shor" and r["status"] == "OK")
    ok = quiet_ok + noisy_ok
    print()
    print(
        f"Live sweep: {ok}/{len(rows)} OK "
        f"({quiet_ok}/{sum(1 for r in rows if r['condition']=='Shaant')} quiet, "
        f"{noisy_ok}/{sum(1 for r in rows if r['condition']=='Shor')} noisy), "
        f"{len(rows) - ok} mismatch/error, "
        f"{sum(1 for r in rows if r['status'] == 'SKIP')} skipped."
    )

    for r in rows:
        if r["status"] == "ERROR":
            print(f"  case {r['id']}: {r['detail']}", file=sys.stderr)
        elif r["status"] == "MISMATCH":
            print(f"  case {r['id']}: {r['detail']}", file=sys.stderr)

    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write("# Live Gnani STT eval\n\n")
            f.write(format_table(rows))
            f.write("\n\n")
        print(f"Markdown written to {args.markdown}", file=sys.stderr)

    if ok == len(rows):
        return 0
    if ok == 0 and any(r["status"] == "SKIP" for r in rows):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
