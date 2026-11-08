"""Voice languages accepted by the app (Gnani Prisma STT / Timbre TTS).

The allow-list here is the only set of codes the API forwards to Gnani; anything
else is rejected with HTTP 400 instead of being passed through.

All ten languages are understood the same way: a number-word table exists for
each one in :mod:`lang_numbers`, composed by the same algorithm Hindi uses, and
native numerals are folded to ASCII digits before parsing.  What differs per
language is the *STT format* (`verbatim` vs `transcribe`): Prisma renders
numbers differently depending on it, and :data:`STT_FORMAT_BY_LANGUAGE` records
the spelling that actually produced correct amounts in ``eval_langs.py`` —
measured with real TTS -> STT round trips, not guessed.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES: dict[str, str] = {
    "hi-IN": "हिन्दी",
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

DEFAULT_LANGUAGE = "hi-IN"

# Every language has a tested number-word table. Kept as an explicit set so a
# future regression ("this table is a stub") is visible rather than implied.
SPOKEN_NUMBER_LANGUAGES: frozenset[str] = frozenset(SUPPORTED_LANGUAGES)

# Prisma's `format` field per language, chosen by eval_langs.py. `verbatim`
# keeps number words (proves the word tables); `transcribe` returns digits,
# which is the better spelling for a language whose words the provider does not
# write consistently.
STT_FORMAT_BY_LANGUAGE: dict[str, str] = {
    "bn-IN": "transcribe",
    "en-IN": "verbatim",
    "gu-IN": "verbatim",
    "hi-IN": "verbatim",
    "kn-IN": "verbatim",
    "ml-IN": "transcribe",
    "mr-IN": "verbatim",
    "pa-IN": "verbatim",
    "ta-IN": "verbatim",
    "te-IN": "verbatim",
}
DEFAULT_STT_FORMAT = "verbatim"


class UnsupportedLanguage(ValueError):
    """Raised for a language code outside the allow-list."""

    def __init__(self, code: str):
        self.code = str(code or "")
        self.supported = tuple(SUPPORTED_LANGUAGES)
        shown = self.code or "(empty)"
        super().__init__(
            f"'{shown}' supported nahi hai. Supported: {', '.join(self.supported)}."
        )


def normalize(code: str | None) -> str:
    """Validate ``code`` against the allow-list and return the canonical form.

    ``hi-IN``/``hi-in`` are both accepted; an empty value means "use the
    configured default" so existing callers keep working.  Anything else
    raises :class:`UnsupportedLanguage`.
    """
    if code is None or not str(code).strip():
        return DEFAULT_LANGUAGE
    wanted = str(code).strip()
    for known in SUPPORTED_LANGUAGES:
        if known.lower() == wanted.lower():
            return known
    raise UnsupportedLanguage(wanted)


def try_normalize(code: str | None) -> str | None:
    """Same as :func:`normalize` but returns ``None`` instead of raising."""
    try:
        return normalize(code)
    except UnsupportedLanguage:
        return None


def speaks_numbers(language: str) -> bool:
    return normalize(language) in SPOKEN_NUMBER_LANGUAGES


def stt_format_for(language: str) -> str:
    """Prisma ``format`` to use for ``language`` (see STT_FORMAT_BY_LANGUAGE)."""
    return STT_FORMAT_BY_LANGUAGE.get(normalize(language), DEFAULT_STT_FORMAT)


def voice_for(language: str) -> tuple[str | None, str, bool]:
    """Resolve the Timbre voice for ``language``.

    Returns ``(voice, language_used, fell_back)``.  ``voice`` is ``None``,
    meaning "use the configured ``GNANI_TTS_VOICE``": every language below has
    been verified by a Timbre -> Prisma round trip in ``eval_langs.py``, so no
    language has to borrow another one's voice any more.
    """
    return None, normalize(language), False


def catalogue() -> list[dict]:
    """Public description of every accepted language, for ``/api/languages``."""
    entries = []
    for code, native_name in SUPPORTED_LANGUAGES.items():
        voice, spoken_in, fell_back = voice_for(code)
        entries.append(
            {
                "code": code,
                "native_name": native_name,
                "spoken_numbers": code in SPOKEN_NUMBER_LANGUAGES,
                "stt_format": stt_format_for(code),
                "voice_available": not fell_back,
                "voice_language": spoken_in,
            }
        )
    return entries
