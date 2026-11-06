"""Live Gnani STT evaluation on *real recorded audio*.

This is the only script in the project that can measure real-world speech
recognition.  Everything else works from fixed transcripts (`eval_report.py`,
`tests/test_stt_parser_evals.py`) or from TTS-generated audio
(`live_eval.py`), which is synthetic speech, not a shop floor.

It never writes to the ledger, never creates customers and never commits a
transaction.  It only prepares audio, transcribes it and parses the result.

Usage:
    python eval_recordings.py --dir recordings/
    python eval_recordings.py --dir recordings/ --only 1,3,13
    python eval_recordings.py --dir recordings/ --markdown recordings_report.md \\
        --csv recordings_report.csv

File naming (this is the whole convention):

    <case_id>__<condition>.<ext>        e.g.   3__quiet.wav
                                        e.g.  13__noisy.m4a

* ``case_id`` is the 1-based ID from the 21-case table in
  ``tests/test_stt_parser_evals.py``; the intended command, amount and customer
  come from that case, so the audio is compared against the same ground truth.
* ``condition`` is a free label you choose — ``quiet``, ``noisy``, ``shop``,
  ``fan-on`` …  It is only used for grouping in the summary.
* Supported containers: WAV, MP3, OGG, FLAC, AAC, M4A (anything FFmpeg can read
  works, including WebM, when FFmpeg is installed).

Exit status:
    0  every supplied recording reproduced the intended command
    1  at least one recording did not
    2  nothing was evaluated (no key, no files, or the provider is unreachable)

See ``docs/noisy-audio-eval.md`` for how to record, how to add synthetic noise
(clearly labelled as synthetic) and how to report the numbers honestly.
"""

from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

from audio_utils import AudioError, prepare_file_for_stt
from gnani_client import is_configured, transcribe
from parser import canonical_name, parse_command

from tests.test_stt_parser_evals import CASES

CASES_BY_ID = {case[0]: case for case in CASES}

SUPPORTED_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a", ".webm", ".mp4"}

HEADERS = ["ID", "Condition", "File", "Live transcript", "Parsed (intent / amount / customer)", "Status"]


def _amount_eq(parsed: Decimal | None, expected: str | None) -> bool:
    if expected is None:
        return parsed is None
    if parsed is None:
        return False
    return parsed == Decimal(expected)


def _customer_eq(parsed: str | None, expected: str | None) -> bool:
    """Script-agnostic comparison, the same key the ledger resolves on."""
    if expected is None:
        return parsed is None
    if parsed is None:
        return False
    return canonical_name(parsed) == canonical_name(expected)


def parse_filename(path: Path) -> tuple[int, str] | None:
    """``3__quiet.wav`` -> ``(3, "quiet")``; returns None when unparseable."""
    stem = path.stem
    if "__" not in stem:
        return None
    case_part, _, condition = stem.partition("__")
    try:
        case_id = int(case_part.strip())
    except ValueError:
        return None
    if case_id not in CASES_BY_ID:
        return None
    return case_id, (condition.strip() or "unlabelled")


def discover(directory: Path) -> list[tuple[Path, int, str]]:
    found: list[tuple[Path, int, str]] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        meta = parse_filename(path)
        if meta is None:
            print(
                f"  skip {path.name}: expected <case_id>__<condition>.<ext> "
                f"(case ids are 1..{max(CASES_BY_ID)})",
                file=sys.stderr,
            )
            continue
        found.append((path, meta[0], meta[1]))
    return found


def evaluate_file(path: Path, case_id: int, condition: str) -> dict:
    _id, _fixture_condition, original, _fixture_transcript, want_intent, want_amount, want_customer = (
        CASES_BY_ID[case_id]
    )

    row = {
        "id": case_id,
        "condition": condition,
        "file": path.name,
        "original": original,
        "transcript": "—",
        "parsed_intent": "—",
        "parsed_amount": "—",
        "parsed_customer": "—",
        "status": "ERROR",
        "detail": "",
    }

    try:
        prepared = prepare_file_for_stt(path)
        result = transcribe(prepared.data)
    except AudioError as exc:
        row["detail"] = f"audio: {exc.code} — {exc.message}"
        return row
    except Exception as exc:  # noqa: BLE001 — provider/network errors are reported, not raised
        row["detail"] = f"{type(exc).__name__}: {exc}"
        return row

    parsed = parse_command(result.transcript)
    row["transcript"] = result.transcript
    row["parsed_intent"] = parsed.intent
    row["parsed_amount"] = str(parsed.amount_rupees) if parsed.amount_rupees is not None else "—"
    row["parsed_customer"] = parsed.customer_name or "—"

    reasons: list[str] = []
    if parsed.intent != want_intent:
        reasons.append(f"intent {parsed.intent!r} != {want_intent!r}")
    if not _customer_eq(parsed.customer_name, want_customer):
        reasons.append(f"customer {parsed.customer_name!r} != {want_customer!r}")
    if not _amount_eq(parsed.amount_rupees, want_amount):
        reasons.append(f"amount {parsed.amount_rupees!r} != {want_amount!r}")

    if reasons:
        row["status"] = "MISMATCH"
        row["detail"] = "; ".join(reasons)
    else:
        row["status"] = "OK"
        row["detail"] = "matched intended command"
    return row


def print_table(rows: list[dict]) -> None:
    widths = [
        max([len(HEADERS[i])] + [len(str(r[key])) for r in rows])
        for i, key in enumerate(["id", "condition", "file", "transcript"])
    ]
    print(" | ".join(HEADERS))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        parsed = f"{row['parsed_intent']} / {row['parsed_amount']} / {row['parsed_customer']}"
        print(
            f"{row['id']} | {row['condition']} | {row['file']} | {row['transcript']} | "
            f"{parsed} | {row['status']}"
        )


def write_markdown(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# Live recording evaluation\n\n")
        handle.write(
            "Audio transcribed by Gnani Prisma and parsed by `parser.py`.  Every row is a\n"
            "real recording **unless** its Condition column says `synthetic` /\n"
            "`synthetic-noise`, in which case the numbers are a stress test, not\n"
            "real-world accuracy.\n\n"
        )
        handle.write(
            "| ID | Condition | File | Spoken phrase (intended) | Live transcript | "
            "Parsed (intent / amount / customer) | Status | Detail |\n"
        )
        handle.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for row in rows:
            parsed = f"{row['parsed_intent']} / {row['parsed_amount']} / {row['parsed_customer']}"
            handle.write(
                f"| {row['id']} | {row['condition']} | {row['file']} | {row['original']} | "
                f"{row['transcript']} | {parsed} | {row['status']} | {row['detail']} |\n"
            )
        ok = sum(1 for row in rows if row["status"] == "OK")
        handle.write(
            f"\n**Result: {ok}/{len(rows)} recordings reproduced the intended command.** "
            f"{len(rows)} clip(s) evaluated; synthetic clips, if any, are labelled in the "
            f"Condition column.\n"
        )


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "condition", "file", "original", "transcript",
                        "parsed_intent", "parsed_amount", "parsed_customer",
                        "status", "detail"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Evaluate real recorded audio against the 21 fixture commands"
    )
    ap.add_argument("--dir", metavar="DIR",
                    help="directory of <case_id>__<condition>.<ext> recordings")
    ap.add_argument("--only", help="comma-separated case IDs to evaluate")
    ap.add_argument("--markdown", metavar="PATH", help="write a Markdown report")
    ap.add_argument("--csv", metavar="PATH", help="write a CSV report")
    ap.add_argument("--list", action="store_true",
                    help="print the 21 phrases to record (no API calls, no key needed)")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.list:
        print("Record each phrase below once per condition, naming the file "
              "<case_id>__<condition>.<ext> (e.g. 3__quiet.wav).")
        print()
        for case in CASES:
            print(f"  {case[0]:>2}  [{case[1]:<6}]  {case[2]}")
        print()
        print("Intended meaning per phrase is the ground truth the parser is "
              "checked against; see tests/test_stt_parser_evals.py.")
        return 0

    if not args.dir:
        print("ERROR: --dir is required (or use --list to print the phrases).", file=sys.stderr)
        return 2

    if not is_configured():
        print(
            "SKIPPED: GNANI_API_KEY is not configured.  Put it in .env, restart the shell "
            "and re-run.  No numbers are reported without a real call.",
            file=sys.stderr,
        )
        return 2

    directory = Path(args.dir)
    if not directory.is_dir():
        print(f"SKIPPED: {directory} is not a directory.", file=sys.stderr)
        return 2

    clips = discover(directory)
    if args.only:
        wanted = {int(part) for part in args.only.split(",") if part.strip()}
        clips = [clip for clip in clips if clip[1] in wanted]

    if not clips:
        print(
            f"SKIPPED: no <case_id>__<condition>.<ext> recordings found in {directory}.",
            file=sys.stderr,
        )
        return 2

    print(f"Transcribing {len(clips)} recording(s) from {directory} …")
    rows = [evaluate_file(path, case_id, condition) for path, case_id, condition in clips]

    print_table(rows)
    ok = sum(1 for row in rows if row["status"] == "OK")
    errors = sum(1 for row in rows if row["status"] == "ERROR")
    print()
    print(f"Recordings: {ok}/{len(rows)} reproduced the intended command, "
          f"{len(rows) - ok - errors} mismatch, {errors} error.")
    for row in rows:
        if row["status"] != "OK":
            print(f"  {row['file']} (case {row['id']}): {row['detail']}", file=sys.stderr)

    if args.markdown:
        write_markdown(args.markdown, rows)
        print(f"Markdown written to {args.markdown}", file=sys.stderr)
    if args.csv:
        write_csv(args.csv, rows)
        print(f"CSV written to {args.csv}", file=sys.stderr)

    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
