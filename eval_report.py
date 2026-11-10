"""
Evaluation report generator for the 21-case HisabSetu AI STT + parser sweep.

The cases, expected intents, amounts and customers are the *same fixtures* used
by `tests/test_stt_parser_evals.py`, so the report and the automated tests stay
in sync by construction rather than by copy-paste.

Usage:
    python eval_report.py              # print Markdown table + CSV to stdout
    python eval_report.py --csv out.csv
    python eval_report.py --markdown report.md

Nothing here calls Gnani and nothing here writes to the ledger.  The parser
stages are pure functions; the STT stage uses the supplied transcripts as
fixed fixtures.
"""

from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal

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
    case_note,
    end_to_end_outcome,
    evaluate_stt_judgement,
    stt_judgement_note,
)

# Re-export the judgement struct so the report can use it directly.
from tests.test_stt_parser_evals import SttJudgement

INTENT_LABEL = {
    INTENT_ADD_CREDIT: "add_credit",
    INTENT_RECORD_PAYMENT: "record_payment",
    INTENT_BALANCE_QUERY: "balance_query",
    INTENT_TOP_DEBTOR: "top_debtor",
    INTENT_DAILY_SUMMARY: "daily_summary",
    INTENT_UNKNOWN: "unknown",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _amount_eq(parsed: Decimal | None, expected: str | None) -> bool:
    if expected is None:
        return parsed is None
    if parsed is None:
        return False
    return parsed == Decimal(expected)


def _customer_eq(parsed: str | None, expected: str | None) -> bool:
    """Customer match through ``canonical_name`` — the ledger's own key.

    ``normalize_name`` alone maps ``सुनीता`` -> ``suneetaa`` and a typed
    ``Sunita`` stays ``sunita``; the ledger links them, so the report must use
    the same comparison or it would keep reporting a fixed bug as a failure.
    """
    if expected is None:
        return parsed is None
    if parsed is None:
        return False
    return canonical_name(parsed) == canonical_name(expected)


def _amount_text(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"₹{value}"


def evaluate(case: tuple[int, str, str, str, str, str | None, str | None]) -> dict:
    """Run both stages for one case and return a flat report row."""
    cid, _condition, original, transcript, want_intent, want_amount, want_customer = case
    parsed = parse_command(transcript)
    judgement = evaluate_stt_judgement(case)

    row_condition = _condition

    # --- STT judgement ---
    stt_status = "stt_ok" if (
        judgement.customer_preserved and judgement.amount_preserved
        and judgement.intent_preserved
    ) else "stt_mismatch"
    stt_detail = judgement.reason

    # --- Parser stage (against the transcript meaning) ---
    parser_notes: list[str] = []
    if want_intent in {INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT} and parsed.amount_rupees is None:
        parser_notes.append("transcript has no usable amount for parser")
    if parsed.intent == INTENT_UNKNOWN and want_intent != INTENT_UNKNOWN:
        parser_notes.append("parser classified the transcript as unknown intent")
    if want_intent in {INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT, INTENT_BALANCE_QUERY}:
        if not _customer_eq(parsed.customer_name, want_customer):
            parser_notes.append(
                f"parser-read customer {parsed.customer_name!r} differs from "
                f"intended {want_customer!r} "
                f"(canonical_name: {canonical_name(parsed.customer_name)!r} vs "
                f"{canonical_name(want_customer)!r})"
            )

    parser_status = "parser_ok"
    if parsed.intent == INTENT_UNKNOWN:
        parser_status = "parser_unknown_intent"

    # --- End-to-end stage ---
    # Same rule the test suite asserts (tests/test_stt_parser_evals.py:
    # end_to_end_outcome), so the report can never disagree with the tests.
    outcome = end_to_end_outcome(case)
    if not outcome.ok:
        e2e_status = "e2e_fail"  # unexplained divergence = parser bug
    elif outcome.stt_loss:
        e2e_status = "e2e_stt_loss"  # transcript lost it; parser read it honestly
    else:
        e2e_status = "e2e_ok"

    reasons = list(outcome.reasons)
    failure_reason = " | ".join(reasons) if reasons else ""
    if outcome.stt_loss:
        failure_reason = (
            failure_reason
            + " — recorded as a TRANSCRIPTION loss, not a parser failure"
        )

    return {
        "id": cid,
        "condition": row_condition,
        "original_phrase": original,
        "stt_transcript": transcript,
        "expected_intent": want_intent,
        "expected_amount": want_amount,
        "expected_customer": want_customer,
        "parsed_intent": parsed.intent,
        "parsed_customer": parsed.customer_name,
        "parsed_amount": str(parsed.amount_rupees) if parsed.amount_rupees is not None else None,
        "stt_status": stt_status,
        "stt_detail": stt_detail,
        "parser_status": parser_status,
        "e2e_status": e2e_status,
        "failure_reason": failure_reason,
        "notes": case_note(cid) or stt_judgement_note(cid) or "",
        "parser_ambiguity": ", ".join(parsed.ambiguity) if parsed.ambiguity else "",
        "parser_reasons": " | ".join(parsed.reasons) if parsed.reasons else "",
    }


def header() -> list[str]:
    return [
        "Test ID",
        "Condition",
        "Original phrase",
        "Actual STT transcript",
        "Expected intent",
        "Expected amount",
        "Expected customer",
        "Parsed intent",
        "Parsed customer",
        "Parsed amount",
        "STT status",
        "STT detail",
        "Parser status",
        "End-to-end status",
        "Failure reason",
    ]


def row_values(r: dict) -> list[str]:
    return [
        str(r["id"]),
        r.get("condition", ""),
        r["original_phrase"],
        r["stt_transcript"],
        r["expected_intent"],
        r["expected_amount"] or "—",
        r["expected_customer"] or "—",
        r["parsed_intent"],
        r["parsed_customer"] or "—",
        r["parsed_amount"] or "—",
        r["stt_status"],
        r["stt_detail"],
        r["parser_status"],
        r["e2e_status"],
        r["failure_reason"],
    ]


def detailed_table(rows: list[dict]) -> str:
    """Styled variant with the extra diagnostic columns."""
    cols = header() + [
        "Parser ambiguity",
        "Parser reasons",
        "Notes",
    ]

    lines: list[str] = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    for r in rows:
        vals = row_values(r) + [
            r.get("parser_ambiguity", "") or "—",
            r.get("parser_reasons", "") or "—",
            r.get("notes", "") or "—",
        ]
        lines.append("| " + " | ".join(str(v) for v in vals) + " |")
    return "\n".join(lines)


def summary(rows: list[dict], quiet: list[tuple] | None = None, noisy: list[tuple] | None = None) -> str:
    stt_ok = sum(1 for r in rows if r["stt_status"] == "stt_ok")
    parser_ok = sum(1 for r in rows if r["parser_status"] == "parser_ok")
    e2e_ok = sum(1 for r in rows if r["e2e_status"] == "e2e_ok")
    e2e_loss = sum(1 for r in rows if r["e2e_status"] == "e2e_stt_loss")
    e2e_fail = sum(1 for r in rows if r["e2e_status"] == "e2e_fail")
    total = len(rows)

    quiet_rows = [r for r in rows if r.get("condition") == "Shaant"]
    noisy_rows = [r for r in rows if r.get("condition") == "Shor"]

    lines: list[str] = []
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total cases: **{total}** (quiet **{len(quiet_rows)}**, noisy **{len(noisy_rows)}**)")
    lines.append(f"- STT judgement: **{stt_ok}/{total}** preserved intent ({sum(1 for r in quiet_rows if r['stt_status']=='stt_ok')}/{len(quiet_rows)} quiet, {sum(1 for r in noisy_rows if r['stt_status']=='stt_ok')}/{len(noisy_rows)} noisy)")
    lines.append(f"- Parser stage: **{parser_ok}/{total}** parsed a command from the supplied transcript")
    lines.append(f"- End-to-end: **{e2e_ok}/{total}** reproduced the intended command exactly")
    lines.append(
        f"- End-to-end, transcription-limited: **{e2e_loss}/{total}** diverged only because the "
        f"supplied transcript lost the command (parser read the transcript faithfully)"
    )
    lines.append(f"- End-to-end failures (parser bugs): **{e2e_fail}/{total}**")
    lines.append("")

    if stt_ok < total:
        lines.append("### STT mismatches (judgement)")
        lines.append("")
        for r in rows:
            if r["stt_status"] != "stt_ok":
                lines.append(f"- **Case {r['id']}**: {r['stt_detail']}")
        lines.append("")

    if e2e_loss:
        lines.append("### End-to-end divergences explained by transcription (not parser bugs)")
        lines.append("")
        for r in rows:
            if r["e2e_status"] == "e2e_stt_loss":
                lines.append(f"- **Case {r['id']}**: {r['failure_reason']}")
        lines.append("")

    if e2e_fail:
        lines.append("### End-to-end failures (parser bugs)")
        lines.append("")
        for r in rows:
            if r["e2e_status"] == "e2e_fail":
                lines.append(f"- **Case {r['id']}**: {r['failure_reason']}")
        lines.append("")
    else:
        lines.append("No end-to-end case failed for a parser reason on the supplied transcripts.")
        lines.append("")

    lines.append("## Condition split")
    lines.append("")
    lines.append("### Quiet audio (Shaant) — cases 1–11")
    lines.append("")
    for r in quiet_rows:
        cond = "stt_ok" if r["stt_status"] == "stt_ok" else "stt_mismatch"
        e2e = r["e2e_status"]
        lines.append(
            f"- **Case {r['id']}**: STT `{cond}`, parser `{r['parser_status']}`, "
            f"e2e `{e2e}` — "
            f"{r['failure_reason'] or 'matched intended command'}."
        )
    lines.append("")
    lines.append("### Noisy audio (Shor) — cases 12–21")
    lines.append("")
    for r in noisy_rows:
        cond = "stt_ok" if r["stt_status"] == "stt_ok" else "stt_mismatch"
        e2e = r["e2e_status"]
        lines.append(
            f"- **Case {r['id']}**: STT `{cond}`, parser `{r['parser_status']}`, "
            f"e2e `{e2e}` — "
            f"{r['failure_reason'] or 'matched intended command'}."
        )
    lines.append("")

    lines.append("## Important limitation")
    lines.append("")
    lines.append(
        "The 11 quiet cases and 10 noisy cases above are transcripts supplied by the author from their own recordings "
        "(one speaker, one device). The audio files are not in this repository, so this report scores the supplied "
        "transcripts. It is a small sample, not a general accuracy figure."
    )
    lines.append("")
    lines.append("These numbers are therefore **not** STT word-error or accuracy metrics:")
    lines.append("")
    lines.append("- they measure our *parser* against fixed transcripts, and")
    lines.append("- the STT column is a per-case human judgement of that supplied transcript.")
    lines.append("")
    lines.append(
        "For a real recording-based measurement see `docs/noisy-audio-eval.md` "
        "(`python live_eval.py` for paid live GNANI STT runs on recorded audio)."
    )
    lines.append("")

    return "\n".join(lines)


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "test_id", "condition", "original_phrase", "stt_transcript",
                "expected_intent", "expected_amount", "expected_customer",
                "parsed_intent", "parsed_customer", "parsed_amount",
                "stt_status", "stt_detail", "parser_status",
                "e2e_status", "failure_reason", "notes",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "test_id": r["id"],
                "condition": r.get("condition", "") or "",
                "original_phrase": r["original_phrase"],
                "stt_transcript": r["stt_transcript"],
                "expected_intent": r["expected_intent"],
                "expected_amount": r["expected_amount"] or "",
                "expected_customer": r["expected_customer"] or "",
                "parsed_intent": r["parsed_intent"],
                "parsed_customer": r["parsed_customer"] or "",
                "parsed_amount": r["parsed_amount"] or "",
                "stt_status": r["stt_status"],
                "stt_detail": r["stt_detail"],
                "parser_status": r["parser_status"],
                "e2e_status": r["e2e_status"],
                "failure_reason": r["failure_reason"],
                "notes": r["notes"],
            })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="HisabSetu AI STT + parser eval report (21 cases: quiet + noisy)"
    )
    ap.add_argument("--markdown", metavar="PATH", help="write styled Markdown table")
    ap.add_argument("--csv", metavar="PATH", help="write CSV report")
    args = ap.parse_args(argv)

    quiet = [c for c in CASES if c[1] == "Shaant"]
    noisy = [c for c in CASES if c[1] == "Shor"]

    rows = [evaluate(c) for c in CASES]

    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(detailed_table(rows))
            f.write("\n\n")
            f.write(summary(rows, quiet=quiet, noisy=noisy))
        print(f"Markdown report written to {args.markdown}", file=sys.stderr)
    else:
        out = detailed_table(rows) + "\n\n" + summary(rows, quiet=quiet, noisy=noisy)
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")

    if args.csv:
        write_csv(args.csv, rows)
        print(f"CSV report written to {args.csv}", file=sys.stderr)

    # Exit status reflects real parser failures only; a transcription-limited
    # divergence is reported explicitly and is not a parser bug.
    return 0 if all(r["e2e_status"] != "e2e_fail" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
