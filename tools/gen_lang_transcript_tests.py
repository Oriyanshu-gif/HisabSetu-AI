"""Regenerate tests/test_lang_transcripts.py from docs/lang-eval.json.

The parser tests must be built from *real* provider output, not invented
strings.  `eval_langs.py` saves every transcript it heard in
docs/lang-eval.json; this script turns those transcripts into parametrised
parser tests, so re-running the eval after a provider change refreshes the
evidence and the tests together.

    python eval_langs.py            # fresh transcripts
    python tools/gen_lang_transcript_tests.py
"""

from __future__ import annotations

import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "lang-eval.json"
TARGET = ROOT / "tests" / "test_lang_transcripts.py"

HEADER = '''"""Parser tests built from REAL Prisma transcripts.

Every string below was produced end to end by `eval_langs.py`: Timbre spoke the
sentence in that language, Prisma transcribed it, and the transcript was saved
in `docs/lang-eval.json`. Nothing here is hand-written test data, so a provider
change that breaks the parser shows up as a failing test with the real
transcript in the message.

Regenerate with: `python tools/gen_lang_transcript_tests.py`
"""

from __future__ import annotations

import collections

import pytest

from parser import INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT, parse_command

INTENTS = {INTENT_ADD_CREDIT: "add_credit", INTENT_RECORD_PAYMENT: "record_payment"}

# (language, real transcript, expected amount, expected intent, what was said)
CASES = [
'''


def pick_language(entry: dict) -> list[tuple[dict, dict]]:
    """One credit, one payment and the largest amount that passed."""
    fmt = entry["chosen_format"]
    good = [
        (sentence, block)
        for sentence in entry["sentences"]
        if (block := sentence.get("formats", {}).get(fmt)) and block.get("passed")
        and block.get("transcript")
    ]
    chosen: list[tuple[dict, dict]] = []
    seen: set[str] = set()
    for sentence, block in good:
        if sentence["intent"] not in seen:
            chosen.append((sentence, block))
            seen.add(sentence["intent"])
    if good:
        biggest = max(good, key=lambda item: item[0]["amount"])
        if biggest not in chosen:
            chosen.append(biggest)
    return chosen[:3]


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    picked: list[tuple[str, dict, dict]] = []
    for code, entry in report["languages"].items():
        for sentence, block in pick_language(entry):
            picked.append((code, sentence, block))

    body = [
        f"    ({code!r}, {block['transcript']!r}, {sentence['amount']},"
        f" INTENTS[{sentence['intent']!r}], {sentence['text']!r}),"
        for code, sentence, block in picked
    ]
    counts = collections.Counter(code for code, _s, _b in picked)
    footer = [
        "]",
        "",
        "",
        '@pytest.mark.parametrize("language, transcript, amount, intent, _said", CASES)',
        "def test_real_transcript_is_understood(language, transcript, amount, intent, _said):",
        "    parsed = parse_command(transcript, language)",
        "    assert parsed.amount_rupees == amount",
        "    assert parsed.intent == intent",
        '    assert parsed.customer_name, f"no customer in {transcript!r}"',
        "    assert parsed.executable is True",
        "",
        "",
        "def test_every_language_has_real_transcripts():",
        "    counts = collections.Counter(case[0] for case in CASES)",
        "    assert len(counts) == 10",
        "    assert min(counts.values()) >= 2",
        "",
    ]
    TARGET.write_text(HEADER + "\n".join(body) + "\n" + "\n".join(footer), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} with {len(picked)} cases: {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
