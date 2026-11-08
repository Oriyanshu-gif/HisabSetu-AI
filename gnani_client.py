"""Thin, testable client for Gnani Prisma STT and Timbre TTS (REST).

Verified against the current official docs (26 Oct 2026):

* Base URL ``https://api.vachana.ai`` (``docs.gnani.ai`` quick start).
* Auth header ``X-API-Key-ID: <key>`` — the docs do **not** use a Bearer scheme.
* STT: ``POST /stt/v3``, multipart fields ``audio_file`` and ``language_code``.
  Response JSON carries the transcript at the top-level ``transcript`` key.
* TTS: ``POST /api/v1/tts/inference`` with JSON ``text``, ``voice``, ``model``,
  ``language``, ``speed`` and ``audio_config``. The response is binary audio.

Both URLs, the auth header/scheme and the voice/model are configurable so a key
provisioned for a different Gnani gateway keeps working.

The API key is never logged, returned in an error message, or sent to the
browser. All errors are converted to :class:`GnaniError` with stable codes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from config import settings

PROVIDER_STT = "gnani-prisma"
PROVIDER_TTS = "gnani-timbre"


class GnaniError(Exception):
    """A safe, user-facing Gnani failure. Never contains the API key."""

    def __init__(self, code: str, message: str, hint: str | None = None, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code


class GnaniNotConfigured(GnaniError):
    def __init__(self, feature: str):
        super().__init__(
            "gnani_not_configured",
            f"Gnani {feature} configure nahi hai (GNANI_API_KEY missing).",
            "Project folder mein .env banayein aur GNANI_API_KEY set karein. "
            "Text workflow API key ke bina bhi kaam karta hai.",
            503,
        )


@dataclass
class SttResult:
    transcript: str
    request_id: str | None = None
    model: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class TtsResult:
    audio: bytes
    content_type: str
    provider: str = PROVIDER_TTS


def is_configured() -> bool:
    return bool(settings.gnani_api_key)


def require_configured(feature: str) -> None:
    """The single configuration gate shared by the HTTP layer and this client.

    ``main.py`` and the client used to run their own ``is_configured()`` checks,
    so the endpoint guard and the actual call could disagree whenever the two
    modules were patched or reloaded independently.  Both now call this one
    function, which reads the same ``config.settings`` object, so a missing key
    always surfaces as :class:`GnaniNotConfigured` -> HTTP 503 with code
    ``gnani_not_configured`` whether it is caught at the endpoint guard or
    inside ``transcribe()``/``synthesize()``.
    """
    if not is_configured():
        raise GnaniNotConfigured(feature)


def _post(url: str, **kwargs) -> httpx.Response:
    """Single choke point so tests can monkeypatch the network."""
    return httpx.post(url, timeout=settings.gnani_timeout_seconds, follow_redirects=False, **kwargs)


def _safe_detail(response: httpx.Response) -> str:
    """Extract a short provider message without leaking credentials."""
    text = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("detail", "message", "error", "error_message"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
    except (json.JSONDecodeError, ValueError):
        body = response.text if response.text else ""
        text = body.strip()
    text = text[:180]
    if settings.gnani_api_key and settings.gnani_api_key in text:
        text = text.replace(settings.gnani_api_key, "[redacted]")
    return text


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if 200 <= status < 300:
        return
    detail = _safe_detail(response)
    suffix = f" ({detail})" if detail else ""
    if status in (401, 403):
        raise GnaniError(
            "gnani_auth_failed",
            f"Gnani API key accept nahi hui (HTTP {status}){suffix}.",
            "GNANI_API_KEY check karein aur app restart karein.",
            502,
        )
    if status == 429:
        raise GnaniError(
            "gnani_rate_limited",
            "Gnani API ne rate limit laga di hai. Thodi der baad try karein.",
            "Ek minute ruk kar phir bolein.",
            429,
        )
    if status == 413:
        raise GnaniError("gnani_payload_too_large", "Audio bahut bada hai.", "30 second tak record karein.", 413)
    if status == 415:
        raise GnaniError("gnani_unsupported_audio", f"Gnani ne audio format accept nahi kiya{suffix}.", None, 422)
    if status >= 500:
        raise GnaniError(
            "gnani_server_error",
            f"Gnani service mein problem hai (HTTP {status}){suffix}.",
            "Kuch der baad try karein; aapka ledger safe hai.",
            502,
        )
    raise GnaniError(
        "gnani_request_failed",
        f"Gnani request fail hui (HTTP {status}){suffix}.",
        None,
        502,
    )


def _network_guard(exc: Exception) -> GnaniError:
    if isinstance(exc, httpx.TimeoutException):
        return GnaniError(
            "gnani_timeout",
            "Gnani API ne time par jawab nahi diya.",
            "Internet check karein aur phir try karein. Koi transaction save nahi hua.",
            504,
        )
    return GnaniError(
        "gnani_network_error",
        "Gnani API se connection nahi ban saka.",
        "Internet ya firewall check karein. Text input se kaam jaari rakh sakte hain.",
        502,
    )


def transcribe(
    wav_bytes: bytes, language: str | None = None, audio_format: str | None = None
) -> SttResult:
    """Run Prisma STT on a WAV file that has already been validated.

    ``audio_format`` is Prisma's ``format`` field (``verbatim`` / ``transcribe``).
    Which one is used per language is decided by ``languages.stt_format_for``:
    the two differ in how they render numbers (words vs digits), and the parser
    keeps whichever spelling actually produced correct amounts in
    ``eval_langs.py``.
    """
    require_configured("speech-to-text")
    if not wav_bytes:
        raise GnaniError("empty_audio", "Recording khaali hai. Phir se bolein.", None, 422)

    data = {
        "language_code": language or settings.gnani_stt_language,
        "format": audio_format or "verbatim",
    }
    try:
        response = _post(
            settings.stt_url,
            headers=settings.auth_headers(),
            files={"audio_file": ("voice.wav", wav_bytes, "audio/wav")},
            data=data,
        )
    except Exception as exc:  # httpx transport errors
        raise _network_guard(exc) from exc

    _raise_for_status(response)

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise GnaniError(
            "gnani_malformed_response",
            "Gnani STT ka jawab samajh nahi aaya (JSON nahi tha).",
            "Thodi der baad try karein.",
        ) from exc

    if not isinstance(payload, dict):
        raise GnaniError("gnani_malformed_response", "Gnani STT response unexpected tha.")

    transcript = payload.get("transcript")
    if transcript is None and isinstance(payload.get("data"), dict):
        transcript = payload["data"].get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise GnaniError(
            "gnani_empty_transcript",
            "Kuch samajh nahi aaya. Saaf bol kar phir try karein.",
            "Mic paas rakhein aur thoda dheere bolein.",
            422,
        )

    return SttResult(
        transcript=" ".join(transcript.split()),
        request_id=payload.get("request_id"),
        model=payload.get("model"),
        raw={key: payload[key] for key in ("success", "request_id", "model") if key in payload},
    )


def synthesize(
    text: str, language: str | None = None, voice: str | None = None
) -> TtsResult:
    """Generate WAV speech with Timbre. Returns binary audio, never JSON audio.

    ``language``/``voice`` are per-request overrides; the shared
    ``settings`` object is only *read*, never mutated, so two requests with
    different languages cannot leak into each other.

    Never returns a "success" result without real audio bytes: an empty body,
    a JSON error payload or a non-WAV body where WAV was promised all raise
    :class:`GnaniError` instead.
    """
    require_configured("text-to-speech")
    clean = " ".join((text or "").split())
    if not clean:
        raise GnaniError("empty_text", "Bole jaane wala text khaali hai.", None, 422)
    if len(clean) > settings.max_tts_chars:
        clean = clean[: settings.max_tts_chars].rstrip()

    payload = {
        "text": clean,
        "voice": voice or settings.gnani_tts_voice,
        "model": settings.gnani_tts_model,
        "language": language or settings.gnani_tts_language,
        "speed": settings.gnani_tts_speed,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }
    try:
        response = _post(settings.tts_url, headers=settings.auth_headers(), json=payload)
    except Exception as exc:
        raise _network_guard(exc) from exc

    _raise_for_status(response)

    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    body = response.content
    if not body:
        raise GnaniError("gnani_empty_audio", "Gnani ne khaali audio bheja.", "Phir try karein.")
    if "json" in content_type:
        detail = _safe_detail(response)
        raise GnaniError(
            "gnani_tts_error",
            f"Gnani TTS ne audio ke bajaye error bheja{f' ({detail})' if detail else ''}.",
            "Text reply screen par dikh raha hai; ledger safe hai.",
        )

    audio = response.content
    if not audio.startswith(b"RIFF") and "wav" in content_type:
        raise GnaniError("gnani_malformed_audio", "Gnani ne valid WAV audio nahi bheja.")
    return TtsResult(audio=audio, content_type=content_type or "audio/wav")
