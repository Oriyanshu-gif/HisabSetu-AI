"""Rewrite the README's "## Languages" section from docs/lang-eval.json.

The README must quote the *measured* numbers, not remembered ones, so the table
is generated from the last eval run:

    python eval_langs.py
    python tools/render_readme_languages.py

The section runs from ``## Languages`` up to the next ``## `` heading.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
REPORT = ROOT / "docs" / "lang-eval.json"

LANGUAGE_NAMES = {
    "hi-IN": "हिन्दी (Hindi/Hinglish)",
    "en-IN": "English",
    "bn-IN": "বাংলা",
    "gu-IN": "ગુજરાતી",
    "kn-IN": "ಕನ್ನಡ",
    "ml-IN": "മലയാളം",
    "mr-IN": "मराठी",
    "pa-IN": "ਪੰਜਾਬੀ",
    "ta-IN": "தமிழ்",
    "te-IN": "తెలుగు",
}

EXAMPLES = {
    "hi-IN": "`dedh sau` → 150, `dhai sau` → 250, `paanch hazaar` → 5000, `150`",
    "en-IN": "`one hundred fifty` → 150, `two thousand five hundred` → 2500, `150`",
    "mr-IN": "`दीडशे` → 150, `अडीचशे` → 250, `पन्नास` → 50, `१५०`",
    "gu-IN": "`દોઢસો` → 150, `અઢીસો` → 250, `પચાસ` → 50, `૧૫૦`",
    "pa-IN": "`ਡੇਢ ਸੌ` → 150, `ਢਾਈ ਸੌ` → 250, `ਪੰਜਾਹ` → 50, `੧੫੦`",
    "bn-IN": "`দেড়শো` → 150, `আড়াইশো` → 250, `পঞ্চাশ` → 50, `১৫০`",
    "kn-IN": "`ನೂರ ಐವತ್ತು` → 150, `ಒಂದೂವರೆ ಸಾವಿರ` → 1500, `ಐವತ್ತು` → 50, `೧೫೦`",
    "ml-IN": "`നൂറ്റമ്പത്` → 150, `ഒന്നര ആയിരം` → 1500, `അമ്പത്` → 50, `൧൫൦`",
    "ta-IN": "`நூற்று ஐம்பது` → 150, `ஆயிரத்து ஐந்நூறு` → 1500, `ஐம்பது` → 50, `௧௫௦`",
    "te-IN": "`నూట యాభై` → 150, `వెయ్యి ఐదు వందలు` → 1500, `యాభై` → 50, `౧౫౦`",
}


def build_section(report: dict) -> str:
    languages = report["languages"]
    codes = list(languages)

    rows = []
    for code in codes:
        entry = languages[code]
        verbatim = entry["summary"]["verbatim"]
        transcribe = entry["summary"]["transcribe"]
        rows.append(
            f"| `{code}` | {LANGUAGE_NAMES.get(code, entry['language'])} | "
            f"{verbatim['passed']}/{verbatim['sentences']} | "
            f"{transcribe['passed']}/{transcribe['sentences']} | "
            f"`{entry['chosen_format']}` |"
        )

    total_passed = sum(languages[c]["summary"][languages[c]["chosen_format"]]["passed"] for c in codes)
    total_sentences = sum(
        languages[c]["summary"][languages[c]["chosen_format"]]["sentences"] for c in codes
    )
    overall = round(100 * total_passed / total_sentences, 1) if total_sentences else 0.0

    example_rows = [f"| `{code}` | {EXAMPLES[code]} |" for code in codes if code in EXAMPLES]

    failures = []
    for code in codes:
        entry = languages[code]
        fmt = entry["chosen_format"]
        for sentence in entry["sentences"]:
            block = sentence.get("formats", {}).get(fmt) or {}
            if block and not block.get("passed"):
                failures.append(
                    f"- `{code}`: said `{sentence['text']}` → heard "
                    f"`{block.get('transcript') or '(no transcript: provider error)'}` → "
                    f"amount {block.get('amount')} (want {sentence['amount']}), "
                    f"intent {block.get('intent')} (want {sentence['intent']})"
                )
        for sentence in entry["sentences"]:
            if sentence.get("error"):
                failures.append(f"- `{code}`: TTS failed — {sentence['error']}")
    failures_text = "\n".join(failures) if failures else "- None."

    return f"""## Languages

A first-run chooser (and a header switch after that) sets the language used for
**both** speech-to-text/spoken replies **and** the entire interface. The choice
lives in `localStorage["hisabsetu_lang"]`; if storage is blocked the app keeps
working in memory with `hi-IN`. Only the ten codes below are accepted — anything
else is rejected with HTTP 400 `invalid_language` before it reaches Gnani.

**All ten understand spoken amounts.** Each language has a number-word table in
`lang_numbers.py` (native script *and* common Latin spellings) that is composed
by the same algorithm as Hindi, and native numerals are folded to ASCII digits
before parsing. There is no "digits only" mode.

### One language setting for voice and UI

`localStorage["hisabsetu_lang"]` is the single source of truth: the first-run
modal, the header `[chosen language | English]` toggle and the globe button all
write it, and changing it switches the STT/TTS voice **and** every visible string
instantly, with no reload. The old interface-only menu (`#ui-lang`,
`localStorage["vk-ui-lang"]`) is gone; old values are migrated on load
(`hi`→`hi-IN`, `hing`→`hi-IN` + Hinglish, `mr`→`mr-IN`, `en`→`en-IN`). When
Hindi is chosen, the modal offers an extra "Hinglish" card — the Roman-script
strings with `hi-IN` voice.

Every user-visible string lives in `static/i18n/<code>.json` (`en, hi, hing, mr,
bn, gu, kn, ml, pa, ta, te`), loaded on demand and cached; English is the
fallback for any missing key, so a key can never render raw. Server-generated
texts (previews, warnings, errors, spoken replies) use the same per-language
tables in `messages.py`, with the same English fallback — never Hinglish for a
non-Hindi request. Every script renders with the bundled Noto Sans families so
nothing shows tofu boxes. `tests/test_i18n.py` fails if any language file is
missing keys versus English.

**The non-English interface translations were AI-generated and need native-speaker
review before public rollout** — they are natural shopkeeper wording, not a
formal word-for-word translation, and may still contain errors.

| Code | Language | Examples that parse |
|---|---|---|
{chr(10).join(example_rows)}

### Measured accuracy (real TTS → STT → parser)

`eval_langs.py` speaks 15 sentences per language with Timbre, transcribes each
one with Prisma *in that language*, parses the transcript, and compares amount,
intent and customer name against what was said. A sentence passes only when all
three match. Both Prisma formats are measured on the same audio; the better one
is what the app actually uses (`STT_FORMAT_BY_LANGUAGE`).

| Code | Language | `verbatim` | `transcribe` | used by the app |
|---|---|---|---|---|
{chr(10).join(rows)}

**{total_passed}/{total_sentences} sentences ({overall}%)** in the format the app
uses. Amounts, half-forms (`dedh sau`, `dhai sau`, `अडीचशे`, `ಒಂದೂವರೆ ಸಾವಿರ`),
thousands and lakh are all exercised. Full transcripts, per sentence:
[docs/lang-eval.md](docs/lang-eval.md) (machine-readable:
[docs/lang-eval.json](docs/lang-eval.json)); regenerate with `python eval_langs.py`.

Failures in the run above:

{failures_text}

### Voices

Every language is synthesized in its own language code on the configured Timbre
voice (`GNANI_TTS_VOICE`, default `Nalini`), with no cross-language fallback.
That is verified by round trip — the eval speaks with Timbre and transcribes the
result with Prisma, and the amount survives — not by a human listening to each
clip. The API still reports `X-Voice-Language` and `X-Voice-Fallback: false` per
request, and a per-request language never mutates `settings`.

### Known limits

- The tables cover units, teens, the tens used for money, hundreds, thousand,
  lakh, crore and each language's half-forms. A mid-ten spelling outside that
  set (for example an unusual contracted form) stays `unknown` rather than
  becoming a wrong amount: the app then answers HTTP 422
  `amount_not_understood` with a retry hint and writes nothing.
- Customer names are matched for Latin and Devanagari script. A name spoken in
  Tamil/Bengali/Gurmukhi/Kannada/Malayalam/Telugu script parses correctly but
  will not match a Latin ledger entry, so the app asks you to pick the customer
  or use "correct details". Amounts are unaffected.
- The eval is 15 sentences per language on one voice; it is evidence, not a
  guarantee for every accent, background noise or speaking rate.

---

"""


def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    section = build_section(report)
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(r"^## Languages\r?\n.*?(?=^## )", re.MULTILINE | re.DOTALL)
    if not pattern.search(text):
        raise SystemExit("README has no '## Languages' section to replace")
    README.write_text(pattern.sub(section.replace("---\n\n", "---\n\n"), text, count=1), encoding="utf-8")
    print("README Languages section updated from docs/lang-eval.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
