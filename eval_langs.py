"""Real end-to-end evaluation for every voice language.

For each language this runs the *actual* pipeline, with no mocks:

    sentence --Timbre TTS--> WAV --Prisma STT--> transcript --parser--> result

Each sentence is transcribed twice, once with Prisma's ``format=verbatim`` and
once with ``format=transcribe``, because the two disagree about numbers (words
vs digits) and the better spelling differs per language.  The script prints
every real transcript, decides which format wins for that language, and writes
``docs/lang-eval.json`` (full detail) and ``docs/lang-eval.md`` (the summary the
README quotes).

Run it with the API key in ``.env``::

    python eval_langs.py                 # all ten languages
    python eval_langs.py ta-IN ml-IN     # a subset
    python eval_langs.py --no-tts        # reuse docs/lang-eval-audio/*.wav
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from decimal import Decimal

from config import settings
from gnani_client import GnaniError, synthesize, transcribe
from languages import SUPPORTED_LANGUAGES, voice_for
from parser import canonical_name, name_similarity, parse_command

INTENT_CREDIT = "add_credit"
INTENT_PAYMENT = "record_payment"

# The amounts the brief asks for, said the way each language says them.
AMOUNT_WORDS: dict[str, dict[int, str]] = {
    "hi-IN": {
        50: "पचास",
        150: "डेढ़ सौ",
        250: "ढाई सौ",
        500: "पाँच सौ",
        1500: "डेढ़ हज़ार",
        2500: "ढाई हज़ार",
        12000: "बारह हज़ार",
        100000: "एक लाख",
    },
    "en-IN": {
        50: "fifty",
        150: "one hundred fifty",
        250: "two hundred fifty",
        500: "five hundred",
        1500: "one thousand five hundred",
        2500: "two thousand five hundred",
        12000: "twelve thousand",
        100000: "one lakh",
    },
    "mr-IN": {
        50: "पन्नास",
        150: "दीडशे",
        250: "अडीचशे",
        500: "पाचशे",
        1500: "दीड हजार",
        2500: "अडीच हजार",
        12000: "बारा हजार",
        100000: "एक लाख",
    },
    "gu-IN": {
        50: "પચાસ",
        150: "દોઢસો",
        250: "અઢીસો",
        500: "પાંચસો",
        1500: "દોઢ હજાર",
        2500: "અઢી હજાર",
        12000: "બાર હજાર",
        100000: "એક લાખ",
    },
    "pa-IN": {
        50: "ਪੰਜਾਹ",
        150: "ਡੇਢ ਸੌ",
        250: "ਢਾਈ ਸੌ",
        500: "ਪੰਜ ਸੌ",
        1500: "ਡੇਢ ਹਜ਼ਾਰ",
        2500: "ਢਾਈ ਹਜ਼ਾਰ",
        12000: "ਬਾਰਾਂ ਹਜ਼ਾਰ",
        100000: "ਇੱਕ ਲੱਖ",
    },
    "bn-IN": {
        50: "পঞ্চাশ",
        150: "দেড়শো",
        250: "আড়াইশো",
        500: "পাঁচশো",
        1500: "দেড় হাজার",
        2500: "আড়াই হাজার",
        12000: "বারো হাজার",
        100000: "এক লাখ",
    },
    "kn-IN": {
        50: "ಐವತ್ತು",
        150: "ನೂರ ಐವತ್ತು",
        250: "ಇನ್ನೂರ ಐವತ್ತು",
        500: "ಐನೂರು",
        1500: "ಒಂದೂವರೆ ಸಾವಿರ",
        2500: "ಎರಡೂವರೆ ಸಾವಿರ",
        12000: "ಹನ್ನೆರಡು ಸಾವಿರ",
        100000: "ಒಂದು ಲಕ್ಷ",
    },
    "ml-IN": {
        50: "അമ്പത്",
        150: "നൂറ്റമ്പത്",
        250: "ഇരുന്നൂറ്റമ്പത്",
        500: "അഞ്ഞൂറ്",
        1500: "ഒന്നര ആയിരം",
        2500: "രണ്ടര ആയിരം",
        12000: "പന്ത്രണ്ട് ആയിരം",
        100000: "ഒരു ലക്ഷം",
    },
    "ta-IN": {
        50: "ஐம்பது",
        150: "நூற்று ஐம்பது",
        250: "இருநூற்று ஐம்பது",
        500: "ஐந்நூறு",
        1500: "ஆயிரத்து ஐந்நூறு",
        2500: "இரண்டாயிரத்து ஐந்நூறு",
        12000: "பன்னிரண்டு ஆயிரம்",
        100000: "ஒரு லட்சம்",
    },
    "te-IN": {
        50: "యాభై",
        150: "నూట యాభై",
        250: "రెండు వందల యాభై",
        500: "ఐదు వందలు",
        1500: "వెయ్యి ఐదు వందలు",
        2500: "రెండు వేల ఐదు వందలు",
        12000: "పన్నెండు వేలు",
        100000: "ఒక లక్ష",
    },
}

NAMES: dict[str, tuple[str, str]] = {
    "hi-IN": ("रमेश", "सुनीता"),
    "en-IN": ("Ramesh", "Sunita"),
    "mr-IN": ("रमेश", "सुनीता"),
    "gu-IN": ("રમેશ", "સુનીતા"),
    "pa-IN": ("ਰਮੇਸ਼", "ਸੁਨੀਤਾ"),
    "bn-IN": ("রমেশ", "সুনীতা"),
    "kn-IN": ("ರಮೇಶ", "ಸುನೀತಾ"),
    "ml-IN": ("രമേശ്", "സുനിത"),
    "ta-IN": ("ரமேஷ்", "சுனிதா"),
    "te-IN": ("రమేష్", "సునీత"),
}

# {name} and {amount} are filled in; every sentence is one instruction.
CREDIT_TEMPLATE: dict[str, str] = {
    "hi-IN": "{name} को {amount} रुपये का उधार लिख दो",
    "en-IN": "{name} ko {amount} rupees credit likh do",
    "mr-IN": "{name}ला {amount} रुपये उधार लिही",
    "gu-IN": "{name}ને {amount} રૂપિયા ઉધાર લખો",
    "pa-IN": "{name} ਨੂੰ {amount} ਰੁਪਏ ਉਧਾਰ ਲਿਖੋ",
    "bn-IN": "{name}কে {amount} টাকা ধার লেখো",
    "kn-IN": "{name}ಗೆ {amount} ರೂಪಾಯಿ ಸಾಲ ಬರೆಯಿರಿ",
    "ml-IN": "{name}ന് {amount} രൂപ കടം എഴുതൂ",
    "ta-IN": "{name}க்கு {amount} ரூபாய் கடன் எழுது",
    "te-IN": "{name}కి {amount} రూపాయలు అప్పు రాయి",
}

PAYMENT_TEMPLATE: dict[str, str] = {
    "hi-IN": "{name} ने {amount} रुपये जमा किए",
    "en-IN": "{name} ne {amount} rupees payment diya",
    "mr-IN": "{name}ने {amount} रुपये जमा केले",
    "gu-IN": "{name}એ {amount} રૂપિયા જમા કર્યા",
    "pa-IN": "{name} ਨੇ {amount} ਰੁਪਏ ਜਮ੍ਹਾ ਕੀਤੇ",
    "bn-IN": "{name} {amount} টাকা জমা দিয়েছে",
    "kn-IN": "{name} {amount} ರೂಪಾಯಿ ಜಮಾ ಮಾಡಿದ್ದಾರೆ",
    "ml-IN": "{name} {amount} രൂപ അടച്ചു",
    "ta-IN": "{name} {amount} ரூபாய் செலுத்தினார்",
    "te-IN": "{name} {amount} రూపాయలు జమ చేశారు",
}

# (amount, intent, use_digits) — fifteen per language.
PLAN: list[tuple[int, str, bool]] = [
    (50, INTENT_CREDIT, False),
    (50, INTENT_PAYMENT, False),
    (150, INTENT_CREDIT, False),
    (150, INTENT_PAYMENT, False),
    (1500, INTENT_CREDIT, False),
    (1500, INTENT_PAYMENT, False),
    (2500, INTENT_CREDIT, False),
    (2500, INTENT_PAYMENT, False),
    (12000, INTENT_CREDIT, False),
    (12000, INTENT_PAYMENT, False),
    (100000, INTENT_CREDIT, False),
    (100000, INTENT_PAYMENT, False),
    (250, INTENT_CREDIT, False),
    (500, INTENT_PAYMENT, False),
    (150, INTENT_CREDIT, True),
]

FORMATS = ("verbatim", "transcribe")
AUDIO_DIR = pathlib.Path("docs") / "lang-eval-audio"
ATTEMPTS = 4
PAUSE_SECONDS = 0.4


def _with_retry(call, what: str):
    """Gnani returns an occasional 502/504 on a single call; retry a few times."""
    last = None
    for attempt in range(ATTEMPTS):
        try:
            return call()
        except GnaniError as exc:
            last = exc
            if attempt + 1 < ATTEMPTS:
                time.sleep(2 + attempt * 4)
    raise last


def build_sentences(code: str) -> list[dict]:
    names = NAMES[code]
    words = AMOUNT_WORDS[code]
    sentences = []
    for index, (amount, intent, digits) in enumerate(PLAN):
        name = names[index % len(names)]
        spoken = str(amount) if digits else words[amount]
        template = CREDIT_TEMPLATE[code] if intent == INTENT_CREDIT else PAYMENT_TEMPLATE[code]
        sentences.append(
            {
                "index": index + 1,
                "text": template.format(name=name, amount=spoken),
                "amount": amount,
                "intent": intent,
                "name": name,
                "digits": digits,
            }
        )
    return sentences


def _bare(text: str) -> str:
    """Letters only, without combining marks: രമേശ് and രമേശ compare equal."""
    import unicodedata

    return "".join(
        char for char in unicodedata.normalize("NFC", text or "")
        if not unicodedata.category(char).startswith("M") and char.isalpha()
    )


def _name_ok(expected: str, actual: str | None) -> bool:
    if not actual:
        return False
    if name_similarity(expected, actual) >= 0.7:
        return True
    if canonical_name(expected) == canonical_name(actual):
        return True
    # Indic scripts are not transliterated for matching, so compare the bare
    # letters too ("രമേശ" vs "രമേശ്").
    bare_expected, bare_actual = _bare(expected), _bare(actual)
    return bool(bare_expected) and bare_expected == bare_actual


def score(sentence: dict, parsed) -> dict:
    amount = None if parsed.amount_rupees is None else int(parsed.amount_rupees)
    return {
        "amount_ok": amount == sentence["amount"],
        "intent_ok": parsed.intent == sentence["intent"],
        "name_ok": _name_ok(sentence["name"], parsed.customer_name),
        "amount": amount,
        "name": parsed.customer_name,
        "intent": parsed.intent,
    }


def run_language(code: str, use_tts: bool) -> dict:
    sentences = build_sentences(code)
    voice, _voice_language, _fell_back = voice_for(code)
    entries = []
    print(f"\n=== {code} ({SUPPORTED_LANGUAGES[code]}) voice={voice or settings.gnani_tts_voice}")
    for sentence in sentences:
        audio_path = AUDIO_DIR / f"{code}-{sentence['index']:02d}.wav"
        entry = dict(sentence)
        entry["formats"] = {}
        try:
            if use_tts or not audio_path.exists():
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                audio_path.write_bytes(
                    _with_retry(
                        lambda: synthesize(sentence["text"], language=code, voice=voice),
                        "tts",
                    ).audio
                )
            audio = audio_path.read_bytes()
        except GnaniError as exc:
            entry["error"] = f"tts: {exc.code} {exc.message[:120]}"
            print(f"  {sentence['index']:2d}. TTS FAIL {exc.code}")
            entries.append(entry)
            continue

        for fmt in FORMATS:
            try:
                transcript = _with_retry(
                    lambda: transcribe(audio, language=code, audio_format=fmt), "stt"
                ).transcript
            except GnaniError as exc:
                entry["formats"][fmt] = {"error": f"{exc.code} {exc.message[:80]}"}
                continue
            time.sleep(PAUSE_SECONDS)
            parsed = parse_command(transcript, code)
            result = score(sentence, parsed)
            result["transcript"] = transcript
            result["passed"] = result["amount_ok"] and result["intent_ok"] and result["name_ok"]
            entry["formats"][fmt] = result

        marks = []
        for fmt in FORMATS:
            data = entry["formats"].get(fmt, {})
            marks.append(f"{fmt[0]}={'ok' if data.get('passed') else 'x'}")
        shown = (
            entry["formats"].get("verbatim", {}).get("transcript")
            or entry["formats"].get("transcribe", {}).get("transcript")
            or entry["formats"].get("transcribe", {}).get("error")
            or "(no transcript)"
        )
        print(f"  {sentence['index']:2d}. {' '.join(marks)}  {sentence['amount']:>6} {sentence['intent'][:6]}  {shown}")
        if shown:
            for fmt in FORMATS:
                data = entry["formats"].get(fmt, {})
                if data and not data.get("passed"):
                    print(
                        f"        {fmt}: amt={data.get('amount')} name={data.get('name')!r} "
                        f"intent={data.get('intent')}  <- {data.get('transcript')}"
                    )
        entries.append(entry)

    summary = {}
    usable = [e for e in entries if e.get("formats")]
    for fmt in FORMATS:
        done = [e["formats"][fmt] for e in usable if fmt in e["formats"]]
        passed = sum(1 for d in done if d.get("passed"))
        summary[fmt] = {
            "sentences": len(done),
            "passed": passed,
            "rate": round(100 * passed / len(done), 1) if done else 0.0,
            "amount_rate": round(100 * sum(1 for d in done if d.get("amount_ok")) / len(done), 1)
            if done
            else 0.0,
        }
    best = max(FORMATS, key=lambda f: (summary[f]["passed"], f == "verbatim"))
    return {
        "code": code,
        "language": SUPPORTED_LANGUAGES[code],
        "voice": voice or settings.gnani_tts_voice,
        "sentences": entries,
        "summary": summary,
        "chosen_format": best,
    }


def write_reports(report: dict, path_json: pathlib.Path, path_md: pathlib.Path) -> None:
    path_json.parent.mkdir(parents=True, exist_ok=True)
    path_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Per-language evaluation (real Gnani calls)",
        "",
        "Generated by `eval_langs.py`: every sentence below was spoken by Timbre TTS,",
        "transcribed by Prisma STT in the language itself, then parsed by the app's",
        "parser. No mocks, no fixtures — the transcripts are what the provider returned.",
        "",
        "A sentence passes only when **amount, intent and customer name** all match.",
        "",
        "| Language | verbatim | transcribe | chosen |",
        "|---|---|---|---|",
    ]
    for code, entry in report["languages"].items():
        summary = entry["summary"]
        lines.append(
            f"| {code} ({entry['language']}) | "
            f"{summary['verbatim']['passed']}/{summary['verbatim']['sentences']} "
            f"({summary['verbatim']['rate']}%) | "
            f"{summary['transcribe']['passed']}/{summary['transcribe']['sentences']} "
            f"({summary['transcribe']['rate']}%) | "
            f"**{entry['chosen_format']}** |"
        )
    lines += ["", "## Failures that remain", ""]
    any_failure = False
    for code, entry in report["languages"].items():
        fmt = entry["chosen_format"]
        failures = [
            s
            for s in entry["sentences"]
            if s.get("formats") and not s["formats"].get(fmt, {}).get("passed")
        ]
        errors = [s for s in entry["sentences"] if s.get("error")]
        if not failures and not errors:
            continue
        any_failure = True
        lines.append(f"### {code} ({entry['chosen_format']})")
        for sentence in failures:
            data = sentence["formats"][fmt]
            lines.append(
                f"- said `{sentence['text']}` → heard `{data.get('transcript')}` → "
                f"amount={data.get('amount')} (want {sentence['amount']}), "
                f"name={data.get('name')!r} (want {sentence['name']}), "
                f"intent={data.get('intent')} (want {sentence['intent']})"
            )
        for sentence in errors:
            lines.append(f"- TTS error: {sentence['error']}")
        lines.append("")
    if not any_failure:
        lines.append("None: every language passed every sentence in its chosen format.")
        lines.append("")
    path_md.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("languages", nargs="*", help="subset of language codes")
    parser.add_argument("--no-tts", action="store_true", help="reuse cached WAVs")
    parser.add_argument("--json", default="docs/lang-eval.json")
    parser.add_argument("--md", default="docs/lang-eval.md")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="keep other languages from the existing report (re-run a subset)",
    )
    args = parser.parse_args(argv)

    codes = args.languages or list(SUPPORTED_LANGUAGES)
    unknown = [code for code in codes if code not in SUPPORTED_LANGUAGES]
    if unknown:
        parser.error(f"unknown language codes: {', '.join(unknown)}")

    path_json = pathlib.Path(args.json)
    report: dict = {"languages": {}}
    if args.merge and path_json.exists():
        report = json.loads(path_json.read_text(encoding="utf-8"))
        report.setdefault("languages", {})
    for code in codes:
        report["languages"][code] = run_language(code, use_tts=not args.no_tts)

    total_pass = total_done = 0
    print("\n=== summary ===")
    for code, entry in report["languages"].items():
        chosen = entry["chosen_format"]
        summary = entry["summary"][chosen]
        total_pass += summary["passed"]
        total_done += summary["sentences"]
        print(
            f"{code}: {summary['passed']}/{summary['sentences']} ({summary['rate']}%) "
            f"with {chosen}  [verbatim {entry['summary']['verbatim']['rate']}%, "
            f"transcribe {entry['summary']['transcribe']['rate']}%]"
        )
    if total_done:
        print(f"overall: {total_pass}/{total_done} ({round(100 * total_pass / total_done, 1)}%)")

    write_reports(report, path_json, pathlib.Path(args.md))
    print(f"\nwrote {args.json} and {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
