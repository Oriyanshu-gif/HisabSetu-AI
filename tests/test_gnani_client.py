"""Gnani client contract tests with a mocked HTTP layer (no charges, no key)."""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest

import gnani_client
from gnani_client import GnaniError, GnaniNotConfigured, synthesize, transcribe

WAV = b"RIFF" + b"\x00" * 60


@pytest.fixture
def configured(monkeypatch):
    fake = replace(gnani_client.settings, gnani_api_key="test-key-123")
    monkeypatch.setattr(gnani_client, "settings", fake)
    return fake


@pytest.fixture
def capture(monkeypatch):
    captured = {}

    def install(response):
        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["headers"] = kwargs.get("headers")
            captured["files"] = kwargs.get("files")
            captured["data"] = kwargs.get("data")
            captured["json"] = kwargs.get("json")
            captured["timeout"] = kwargs.get("timeout")
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(gnani_client, "_post", fake_post)
        return captured

    return install


# ---------------------------------------------------------------------------
# Speech to text
# ---------------------------------------------------------------------------


def test_transcribe_success_contract(configured, capture):
    captured = capture(
        httpx.Response(
            200,
            json={
                "success": True,
                "request_id": "req_1",
                "transcript": "  Ramesh ko dedh sau udhaar  ",
                "model": "gnani-prisma-v2.5",
            },
        )
    )
    result = transcribe(WAV)
    assert result.transcript == "Ramesh ko dedh sau udhaar"
    assert result.request_id == "req_1"
    assert result.model == "gnani-prisma-v2.5"

    assert captured["url"] == "https://api.vachana.ai/stt/v3"
    assert captured["headers"] == {"X-API-Key-ID": "test-key-123"}
    assert "audio_file" in captured["files"]
    filename, payload, mime = captured["files"]["audio_file"]
    assert filename == "voice.wav"
    assert payload == WAV
    assert mime == "audio/wav"
    assert captured["data"]["language_code"] == "hi-IN"


def test_transcribe_custom_language(configured, capture):
    captured = capture(httpx.Response(200, json={"transcript": "hello"}))
    transcribe(WAV, language="en-IN")
    assert captured["data"]["language_code"] == "en-IN"


def test_transcribe_auth_failure_never_leaks_key(configured, capture):
    capture(httpx.Response(401, json={"detail": "invalid key test-key-123"}))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_auth_failed"
    assert error.value.status_code == 502
    assert "test-key-123" not in error.value.message
    assert "[redacted]" in error.value.message


def test_transcribe_rate_limit(configured, capture):
    capture(httpx.Response(429, json={"message": "slow down"}))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_rate_limited"
    assert error.value.status_code == 429


def test_transcribe_malformed_json(configured, capture):
    capture(httpx.Response(200, text="<html>gateway</html>"))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_malformed_response"


def test_transcribe_empty_transcript(configured, capture):
    capture(httpx.Response(200, json={"success": True, "transcript": "   "}))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_empty_transcript"


def test_transcribe_timeout(configured, capture):
    capture(httpx.TimeoutException("too slow"))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_timeout"
    assert "transaction" in (error.value.hint or "").lower()


def test_transcribe_network_error(configured, capture):
    capture(httpx.ConnectError("no dns"))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_network_error"


def test_transcribe_server_error(configured, capture):
    capture(httpx.Response(503, text="upstream down"))
    with pytest.raises(GnaniError) as error:
        transcribe(WAV)
    assert error.value.code == "gnani_server_error"


def test_transcribe_requires_configuration(monkeypatch):
    monkeypatch.setattr(gnani_client, "settings", replace(gnani_client.settings, gnani_api_key=""))
    with pytest.raises(GnaniNotConfigured):
        transcribe(WAV)


def test_transcribe_rejects_empty_audio(configured):
    with pytest.raises(GnaniError) as error:
        transcribe(b"")
    assert error.value.code == "empty_audio"


# ---------------------------------------------------------------------------
# Text to speech
# ---------------------------------------------------------------------------


def test_synthesize_success_contract(configured, capture):
    captured = capture(
        httpx.Response(200, content=b"RIFF" + b"\x00" * 200, headers={"content-type": "audio/wav"})
    )
    result = synthesize("नमस्ते, आपका हिसाब तैयार है।")
    assert result.audio.startswith(b"RIFF")
    assert result.content_type == "audio/wav"

    assert captured["url"] == "https://api.vachana.ai/api/v1/tts/inference"
    body = captured["json"]
    assert body["voice"] == "Nalini"
    assert body["model"] == "timbre-v2.5"
    assert body["language"] == "hi-IN"
    assert body["audio_config"]["container"] == "wav"
    assert body["audio_config"]["encoding"] == "linear_pcm"
    assert body["audio_config"]["sample_rate"] == 48000
    assert body["text"].startswith("नमस्ते")


def test_synthesize_accepts_bearer_configuration(monkeypatch, capture):
    fake = replace(
        gnani_client.settings,
        gnani_api_key="abc123",
        gnani_auth_header="Authorization",
        gnani_auth_scheme="Bearer",
    )
    monkeypatch.setattr(gnani_client, "settings", fake)
    captured = capture(httpx.Response(200, content=b"RIFFxxxx", headers={"content-type": "audio/wav"}))
    synthesize("test")
    assert captured["headers"] == {"Authorization": "Bearer abc123"}


def test_synthesize_truncates_to_configured_limit(configured, capture):
    captured = capture(httpx.Response(200, content=b"RIFFxxxx", headers={"content-type": "audio/wav"}))
    synthesize("क" * 900)
    assert len(captured["json"]["text"]) == configured.max_tts_chars


def test_synthesize_error_json_is_not_audio(configured, capture):
    capture(httpx.Response(200, json={"detail": "voice not found"}))
    with pytest.raises(GnaniError) as error:
        synthesize("test")
    assert error.value.code == "gnani_tts_error"
    assert "voice not found" in error.value.message


def test_synthesize_provider_error(configured, capture):
    capture(httpx.Response(400, json={"message": "unsupported language"}))
    with pytest.raises(GnaniError) as error:
        synthesize("test")
    assert error.value.code == "gnani_request_failed"
    assert "unsupported language" in error.value.message


def test_synthesize_not_configured(monkeypatch):
    monkeypatch.setattr(gnani_client, "settings", replace(gnani_client.settings, gnani_api_key=""))
    with pytest.raises(GnaniNotConfigured):
        synthesize("test")


def test_synthesize_rejects_empty_text(configured):
    with pytest.raises(GnaniError) as error:
        synthesize("   ")
    assert error.value.code == "empty_text"
