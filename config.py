"""Runtime configuration for KhataVaani.

Everything is read from environment variables (or a local ``.env`` file).
Secrets are never written to logs, API responses or the frontend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone, tzinfo
from pathlib import Path

try:  # Windows needs the tzdata wheel; fall back to a fixed offset if absent.
    from zoneinfo import ZoneInfo

    IST: tzinfo = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - only on systems without tzdata
    IST = timezone(timedelta(hours=5, minutes=30), "IST")

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Captured *before* load_dotenv() so /api/health can explain where the key came
# from.  A blank GNANI_API_KEY already present in the process environment wins
# over .env (load_dotenv does not override), which is the classic "the key is
# right there in .env but the app says it is not configured" failure.
_PROCESS_KEY_RAW = os.environ.get("GNANI_API_KEY")

load_dotenv(BASE_DIR / ".env", override=False)


def gnani_key_source() -> str:
    """Where ``GNANI_API_KEY`` came from — never the value itself.

    Returns ``process_env``, ``env_file`` or ``none``.  ``process_env`` with an
    empty value means the environment blanked the key and ``.env`` was ignored.
    """
    if _PROCESS_KEY_RAW is not None:
        return "process_env" if _PROCESS_KEY_RAW.strip() else "process_env_empty"
    if os.environ.get("GNANI_API_KEY", "").strip():
        return "env_file"
    return "none"


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable settings snapshot, created once at import time."""

    gnani_api_key: str = field(default_factory=lambda: _env("GNANI_API_KEY"))
    # Current official docs (docs.gnani.ai) use https://api.vachana.ai and the
    # X-API-Key-ID header. Both are configurable so a key issued for another
    # Gnani gateway can be used without code changes.
    gnani_base_url: str = field(
        default_factory=lambda: _env("GNANI_BASE_URL", "https://api.vachana.ai").rstrip("/")
    )
    gnani_auth_header: str = field(
        default_factory=lambda: _env("GNANI_AUTH_HEADER", "X-API-Key-ID")
    )
    gnani_auth_scheme: str = field(
        default_factory=lambda: _env("GNANI_AUTH_SCHEME", "")  # e.g. "Bearer"
    )
    gnani_stt_path: str = field(default_factory=lambda: _env("GNANI_STT_PATH", "/stt/v3"))
    gnani_stt_language: str = field(
        default_factory=lambda: _env("GNANI_STT_LANGUAGE", "hi-IN")
    )
    gnani_tts_path: str = field(
        default_factory=lambda: _env("GNANI_TTS_PATH", "/api/v1/tts/inference")
    )
    gnani_tts_model: str = field(
        default_factory=lambda: _env("GNANI_TTS_MODEL", "timbre-v2.5")
    )
    gnani_tts_voice: str = field(default_factory=lambda: _env("GNANI_TTS_VOICE", "Nalini"))
    gnani_tts_language: str = field(
        default_factory=lambda: _env("GNANI_TTS_LANGUAGE", "hi-IN")
    )
    gnani_tts_speed: float = field(
        default_factory=lambda: float(_env("GNANI_TTS_SPEED", "1.0") or 1.0)
    )
    gnani_timeout_seconds: float = field(
        default_factory=lambda: float(_env("GNANI_TIMEOUT_SECONDS", "30") or 30)
    )
    database_url: str = field(
        default_factory=lambda: _env("VOICE_KHATA_DB_URL", "sqlite:///./voice_khata.db")
    )
    seed_sample_data: bool = field(
        default_factory=lambda: _env("VOICE_KHATA_SEED", "1") != "0"
    )
    max_audio_bytes: int = field(default_factory=lambda: _env_int("MAX_AUDIO_BYTES", 8_000_000))
    max_record_seconds: int = field(default_factory=lambda: _env_int("MAX_RECORD_SECONDS", 30))
    pending_ttl_minutes: int = field(default_factory=lambda: _env_int("PENDING_TTL_MINUTES", 15))
    max_amount_rupees: int = field(default_factory=lambda: _env_int("MAX_AMOUNT_RUPEES", 10_000_000))
    max_tts_chars: int = field(default_factory=lambda: _env_int("MAX_TTS_CHARS", 400))
    ffmpeg_path: str = field(default_factory=lambda: _env("FFMPEG_PATH"))
    ist: tzinfo = field(default_factory=lambda: IST)

    @property
    def gnani_configured(self) -> bool:
        return bool(self.gnani_api_key)

    @property
    def stt_url(self) -> str:
        return f"{self.gnani_base_url}{self.gnani_stt_path}"

    @property
    def tts_url(self) -> str:
        return f"{self.gnani_base_url}{self.gnani_tts_path}"

    def auth_headers(self) -> dict[str, str]:
        """Build auth headers without ever logging the key."""
        token = self.gnani_api_key
        if self.gnani_auth_scheme:
            token = f"{self.gnani_auth_scheme} {token}"
        return {self.gnani_auth_header: token}


settings = Settings()
