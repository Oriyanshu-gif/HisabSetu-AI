"""Voice-language tests: allow-list, per-request override, and the parser paths.

What is pinned here is exactly what the README claims:

* only the 10 Gnani codes are accepted (anything else is a 400);
* a per-request language never leaks into the shared settings object;
* digits work in every language, number words only in hi/en + mr/gu/pa;
* a language with no amount gets a friendly retry error, never a guess.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import gnani_client
import main
from conftest import make_customer, make_wav
from gnani_client import SttResult, TtsResult
from parser import INTENT_ADD_CREDIT, parse_command

SUPPORTED = [
    "hi-IN",
    "en-IN",
    "bn-IN",
    "gu-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
]


@pytest.fixture
def gnani_configured(monkeypatch):
    fake = replace(gnani_client.settings, gnani_api_key="test-key-123")
    monkeypatch.setattr(gnani_client, "settings", fake)
    return fake


# ---------------------------------------------------------------------------
# Allow-list
# ---------------------------------------------------------------------------


def test_languages_endpoint_lists_exactly_the_allow_list(client):
    body = client.get("/api/languages").json()
    assert [entry["code"] for entry in body["languages"]] == SUPPORTED
    assert body["default"] == "hi-IN"


def test_every_language_understands_spoken_amounts(client):
    entries = {entry["code"]: entry for entry in client.get("/api/languages").json()["languages"]}
    assert set(entries) == set(SUPPORTED)
    # No language is "digits only" any more: every code has a tested
    # number-word table, so none of them advertises a reduced capability.
    assert all(entry["spoken_numbers"] for entry in entries.values())
    assert not any("digits_only" in entry for entry in entries.values())
    assert all(entry["voice_available"] for entry in entries.values())
    assert all(entry["stt_format"] in {"verbatim", "transcribe"} for entry in entries.values())


def test_every_entry_has_a_native_name(client):
    for entry in client.get("/api/languages").json()["languages"]:
        assert entry["native_name"].strip()
        assert entry["voice_language"] in SUPPORTED


def test_stt_rejects_an_unsupported_language(client, gnani_configured):
    response = client.post(
        "/api/stt",
        files={"file": ("voice.wav", make_wav(1), "audio/wav")},
        data={"language": "fr-FR"},
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_language"
    assert "fr-FR" in error["message"]


def test_tts_rejects_an_unsupported_language(client, gnani_configured):
    response = client.post("/api/tts", json={"text": "नमस्ते", "language": "de-DE"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_language"


def test_command_rejects_an_unsupported_language(client):
    response = client.post(
        "/api/command",
        json={"text": "Ramesh 150 udhaar", "language": "xx-IN"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_language"


def test_language_is_case_insensitive_and_absent_means_default(client, gnani_configured, monkeypatch):
    seen = {}

    def fake_transcribe(_audio, language=None, audio_format=None):
        seen["language"] = language
        seen["audio_format"] = audio_format
        return SttResult(transcript="Ramesh ko sau ka udhaar")

    monkeypatch.setattr(main, "transcribe", fake_transcribe)
    response = client.post(
        "/api/stt",
        files={"file": ("voice.wav", make_wav(1), "audio/wav")},
        data={"language": "MR-in"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["language"] == "mr-IN"
    assert seen["language"] == "mr-IN"


# ---------------------------------------------------------------------------
# Per-request override never leaks into settings
# ---------------------------------------------------------------------------


def test_stt_language_override_does_not_change_settings(client, gnani_configured, monkeypatch):
    before = gnani_client.settings.gnani_stt_language
    seen = {}

    def fake_transcribe(_audio, language=None, audio_format=None):
        seen["language"] = language
        seen["audio_format"] = audio_format
        return SttResult(transcript="Ramesh 150 udhaar")

    monkeypatch.setattr(main, "transcribe", fake_transcribe)
    response = client.post(
        "/api/stt",
        files={"file": ("voice.wav", make_wav(1), "audio/wav")},
        data={"language": "ta-IN"},
    )
    assert response.status_code == 200
    assert seen["language"] == "ta-IN"
    # The per-language Prisma format chosen by eval_langs.py is applied.
    assert seen["audio_format"] == "verbatim"
    assert gnani_client.settings.gnani_stt_language == before


def test_tts_language_override_does_not_change_settings(client, gnani_configured, monkeypatch):
    before = (
        gnani_client.settings.gnani_tts_language,
        gnani_client.settings.gnani_tts_voice,
    )
    seen = {}

    def fake_synthesize(text, language=None, voice=None):
        seen["language"] = language
        seen["voice"] = voice
        return TtsResult(audio=b"RIFF" + b"\x00" * 64, content_type="audio/wav")

    monkeypatch.setattr(main, "synthesize", fake_synthesize)
    response = client.post("/api/tts", json={"text": "નમસ્તે", "language": "gu-IN"})
    assert response.status_code == 200
    # Gujarati is spoken in Gujarati, on the configured voice, with no fallback.
    assert seen["language"] == "gu-IN"
    assert seen["voice"] is None
    assert response.headers["x-voice-fallback"] == "false"
    assert response.headers["x-voice-language"] == "gu-IN"
    assert (
        gnani_client.settings.gnani_tts_language,
        gnani_client.settings.gnani_tts_voice,
    ) == before


def test_tts_keeps_hindi_on_the_configured_voice(client, gnani_configured, monkeypatch):
    seen = {}

    def fake_synthesize(text, language=None, voice=None):
        seen["language"] = language
        seen["voice"] = voice
        return TtsResult(audio=b"RIFF" + b"\x00" * 64, content_type="audio/wav")

    monkeypatch.setattr(main, "synthesize", fake_synthesize)
    response = client.post("/api/tts", json={"text": "नमस्ते", "language": "hi-IN"})
    assert response.status_code == 200
    assert seen["language"] == "hi-IN"
    assert seen["voice"] is None  # None means "use GNANI_TTS_VOICE"
    assert response.headers["x-voice-fallback"] == "false"


# ---------------------------------------------------------------------------
# Parser: digits everywhere, number words only where tested
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", SUPPORTED)
def test_digit_amounts_work_in_every_language(language):
    parsed = parse_command("Ramesh 150 udhaar", language)
    assert parsed.amount_rupees == 150
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.customer_name.lower().startswith("ramesh")


@pytest.mark.parametrize(
    "text, language, expected",
    [
        ("રમેશ બે સો ઉધાર", "gu-IN", 200),
        ("રમેશ બે સો પચાસ ઉધાર", "gu-IN", 250),
        ("રમેશ દોઢ સો ઉધાર", "gu-IN", 150),
        ("રમેશ ૫૦ ઉધાર", "gu-IN", 50),
        ("रमेशला पन्नास उधार", "mr-IN", 50),
        ("रमेशला दीडशे उधार", "mr-IN", 150),
        ("रमेशला अडीचशे उधार", "mr-IN", 250),
        ("ਰਮੇਸ਼ ਪੰਜਾਹ ਉਧਾਰ", "pa-IN", 50),
        ("ਰਮੇਸ਼ ਢਾਈ ਸੌ ਉਧਾਰ", "pa-IN", 250),
        ("রমেশ পঞ্চাশ ধার", "bn-IN", 50),
        ("রমেশ পাঁচশো ধার", "bn-IN", 500),
        ("ರಮೇಶ ಐವತ್ತು ಸಾಲ", "kn-IN", 50),
        ("ರಮೇಶ ನೂರ ಐವತ್ತು ಸಾಲ", "kn-IN", 150),
        ("രമേശ് അമ്പത് കടം", "ml-IN", 50),
        ("രമേശ് നൂറ്റമ്പത് കടം", "ml-IN", 150),
        ("ரமேஷ் ஐம்பது கடன்", "ta-IN", 50),
        ("ரமேஷ் நூற்று ஐம்பது கடன்", "ta-IN", 150),
        ("రమేష్ యాభై అప్పు", "te-IN", 50),
        ("రమేష్ నూట యాభై అప్పు", "te-IN", 150),
    ],
)
def test_number_words_in_every_language(text, language, expected):
    parsed = parse_command(text, language)
    assert parsed.amount_rupees == expected
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.customer_name


@pytest.mark.parametrize("language", ["bn-IN", "kn-IN", "ml-IN", "ta-IN", "te-IN"])
def test_a_word_outside_the_language_table_is_not_guessed(language):
    # "hazaar" is not a word in these tables; it must not silently become ₹1000.
    parsed = parse_command("Ramesh hazaar udhaar", language)
    assert parsed.amount_rupees is None


def test_english_number_words_parse():
    assert parse_command("Ramesh ko one hundred fifty rupees udhaar", "en-IN").amount_rupees == 150
    assert parse_command("Sunita ne fifty rupees payment diya", "en-IN").amount_rupees == 50


def test_hindi_behaviour_is_unchanged():
    parsed = parse_command("Ramesh ko dedh sau ka udhaar likh do")
    assert parsed.amount_rupees == 150
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.customer_name == "Ramesh"
    assert parsed.executable is True


def test_english_uses_the_hinglish_vocabulary():
    assert parse_command("Ramesh ko dedh sau udhaar", "en-IN").amount_rupees == 150
    assert parse_command("Ramesh 150 udhaar", "en-IN").amount_rupees == 150


# ---------------------------------------------------------------------------
# No amount: friendly retry error, never a guess
# ---------------------------------------------------------------------------


def test_missing_amount_in_another_language_returns_a_retry_error(client, db):
    make_customer(db, "Ramesh")
    response = client.post(
        "/api/command",
        json={"text": "ரமேஷ் கடன்", "language": "ta-IN", "source": "voice"},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "amount_not_understood"
    # The active language wins; English is the fallback when a table has no
    # entry for the key, never Hinglish.
    assert "amount was not understood" in error["message"].lower()
    assert "150" in error["hint"]
    # Nothing was written.
    assert client.get("/api/dashboard").json()["transaction_count"] == 0


def test_hindi_missing_amount_still_uses_the_old_clarification(client, db):
    make_customer(db, "Ramesh")
    response = client.post("/api/command", json={"text": "Ramesh ko udhaar likh do"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "clarification"
    assert "amount" in body["clarification"]["needs"]


def test_digit_command_in_another_language_reaches_a_proposal(client, db):
    customer = make_customer(db, "Ramesh")
    response = client.post(
        "/api/command",
        json={"text": "Ramesh 150 udhaar", "language": "ta-IN"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "proposal"
    assert body["proposal"]["customer"]["id"] == customer.id
    assert body["proposal"]["amount_text"] == "₹150"
