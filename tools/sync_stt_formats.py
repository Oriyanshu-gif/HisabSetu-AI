"""Sync `languages.STT_FORMAT_BY_LANGUAGE` with the last eval run.

`eval_langs.py` measures both Prisma formats per language and records the winner
in docs/lang-eval.json.  The app must use exactly that winner, so this script
rewrites the dict in languages.py (and nothing else) from the report.

    python eval_langs.py
    python tools/sync_stt_formats.py
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "lang-eval.json"
LANGUAGES_PY = ROOT / "languages.py"
BLOCK = re.compile(r"STT_FORMAT_BY_LANGUAGE: dict\[str, str\] = \{.*?\n\}", re.DOTALL)


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    chosen = {
        code: entry["chosen_format"] for code, entry in report["languages"].items()
    }
    lines = ["STT_FORMAT_BY_LANGUAGE: dict[str, str] = {"]
    for code in sorted(chosen):
        lines.append(f'    "{code}": "{chosen[code]}",')
    lines.append("}")
    block = "\n".join(lines)

    text = LANGUAGES_PY.read_text(encoding="utf-8")
    if not BLOCK.search(text):
        raise SystemExit("STT_FORMAT_BY_LANGUAGE block not found in languages.py")
    LANGUAGES_PY.write_text(BLOCK.sub(block, text, count=1), encoding="utf-8")
    print("STT_FORMAT_BY_LANGUAGE updated:", chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
