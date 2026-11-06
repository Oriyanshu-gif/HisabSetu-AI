"""Audio validation and genuine server-side conversion.

Browsers record WebM/Opus (Chrome, Edge, Firefox) or MP4/AAC (Safari). Gnani's
Prisma REST endpoint accepts WAV, MP3, OGG, FLAC, AAC and M4A. WebM is *not*
on that list, so a WebM recording is decoded and re-encoded with FFmpeg into a
16 kHz mono WAV — never renamed.

If FFmpeg is unavailable the API returns a clear, actionable error instead of
sending an unsupported container.
"""

from __future__ import annotations

import functools
import io
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

from config import settings

FFMPEG_INSTALL_HINT = (
    "FFmpeg install karein: PowerShell mein `winget install Gyan.FFmpeg` chalayein, "
    "phir terminal restart karein. Ya `pip install imageio-ffmpeg` karein."
)

SUPPORTED_DIRECT = {"wav", "mp3", "ogg", "flac", "aac", "m4a"}


class AudioError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status_code = status_code


@dataclass
class PreparedAudio:
    data: bytes
    original_format: str | None
    content_type: str
    converted: bool
    duration_seconds: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    details: dict = field(default_factory=dict)


def sniff_format(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if data[4:8] == b"ftyp":
        return "mp4"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if data[:4] == b"fLaC":
        return "flac"
    return None


@functools.lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    """Locate FFmpeg from config, PATH, or the optional imageio-ffmpeg wheel."""
    configured = settings.ffmpeg_path
    if configured:
        candidate = Path(configured)
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:  # optional convenience dependency, never required at import time
        import imageio_ffmpeg

        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if candidate and Path(candidate).is_file():
            return candidate
    except Exception:  # pragma: no cover - optional dependency
        return None
    return None


def ffmpeg_available() -> bool:
    return find_ffmpeg() is not None


def _wav_data_offset(data: bytes) -> int | None:
    """Offset of the PCM ``data`` chunk payload, or None if not parseable."""
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        chunk_size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        if chunk_id == b"data":
            return pos + 8
        # A streaming encoder writes 0xFFFFFFFF here, so stop walking.
        if chunk_size == 0xFFFFFFFF or chunk_size > len(data) - (pos + 8):
            return None
        pos += 8 + chunk_size + (chunk_size & 1)
    return None


def wav_info(data: bytes) -> dict:
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            frames = reader.getnframes()
            rate = reader.getframerate()
            channels = reader.getnchannels()
            width = reader.getsampwidth()
            # Streaming encoders (Gnani Timbre included) write 0xFFFFFFFF as the
            # RIFF/data chunk size, so wave reports a bogus frame count. Clamp to
            # the audio bytes actually present so the duration stays truthful.
            if rate and channels and width:
                start = _wav_data_offset(data)
                if start is not None:
                    available = max(len(data) - start, 0)
                    frames = min(frames, available // (channels * width))
            return {
                "sample_rate": rate,
                "channels": channels,
                "sample_width": width,
                "duration_seconds": round(frames / rate, 2) if rate else None,
            }
    except (wave.Error, EOFError) as exc:
        raise AudioError(
            "invalid_wav",
            "Yeh WAV file padhi nahi ja saki.",
            "Recording dobara karein ya WAV format mein upload karein.",
        ) from exc


def _convert_with_ffmpeg(data: bytes, source_format: str) -> bytes:
    exe = find_ffmpeg()
    if not exe:
        raise AudioError(
            "ffmpeg_missing",
            "Browser ne WebM/MP4 mein record kiya hai, jise convert karne ke liye FFmpeg chahiye.",
            FFMPEG_INSTALL_HINT,
            status_code=503,
        )

    suffix = {"webm": ".webm", "mp4": ".m4a", "ogg": ".ogg", "mp3": ".mp3",
              "aac": ".aac", "flac": ".flac", "wav": ".wav"}.get(source_format, ".bin")
    with tempfile.TemporaryDirectory(prefix="voice_khata_") as tmp:
        source = Path(tmp) / f"input{suffix}"
        target = Path(tmp) / "output.wav"
        source.write_bytes(data)
        command = [
            exe,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(target),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=90, check=False)
        except subprocess.TimeoutExpired as exc:
            raise AudioError(
                "conversion_timeout",
                "Audio convert karne mein bahut zyada samay laga.",
                "Chhoti recording (30 second tak) bhejein.",
                504,
            ) from exc
        if completed.returncode != 0 or not target.exists():
            detail = (completed.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            safe_detail = detail[-1][:200] if detail else "unknown ffmpeg error"
            raise AudioError(
                "conversion_failed",
                f"Audio convert nahi ho saka ({safe_detail}).",
                "Recording saaf karein ya WAV file bhejein. FFmpeg install hai?",
            )
        converted = target.read_bytes()
        if not converted.startswith(b"RIFF") or len(converted) < 44:
            raise AudioError("conversion_failed", "Converted audio valid WAV nahi hai.")
        return converted


def prepare_for_stt(
    data: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> PreparedAudio:
    """Validate an upload and return something Prisma STT can accept."""
    if not data:
        raise AudioError("empty_audio", "Recording khaali hai. Mic check karke phir bolein.")
    if len(data) > settings.max_audio_bytes:
        raise AudioError(
            "audio_too_large",
            f"Audio {settings.max_audio_bytes // 1_000_000} MB se bada hai.",
            "30 second tak hi record karein.",
            413,
        )

    detected = sniff_format(data)
    declared = (content_type or "").split(";")[0].strip().lower()

    details: dict = {
        "declared_content_type": declared or None,
        "filename": filename,
    }

    if detected == "wav":
        info = wav_info(data)
        if info["duration_seconds"] and info["duration_seconds"] > 65:
            raise AudioError(
                "audio_too_long",
                "Recording bahut lambi hai (60 second se zyada).",
                f"Sirf {settings.max_record_seconds} second tak bolein.",
            )
        # Prisma documents 8 kHz - 44.1 kHz input. Timbre produces 48 kHz
        # WAVs, so a round-trip or a desktop recording must be resampled.
        if info["sample_rate"] is not None and not 8000 <= info["sample_rate"] <= 44100:
            if not find_ffmpeg():
                raise AudioError(
                    "wav_needs_conversion",
                    f"Yeh WAV {info['sample_rate']} Hz hai; Gnani 8-44.1 kHz leta hai aur FFmpeg nahi mila.",
                    FFMPEG_INSTALL_HINT,
                    status_code=503,
                )
            converted_data = _convert_with_ffmpeg(data, "wav")
            new_info = wav_info(converted_data)
            details["converted_from_rate"] = info["sample_rate"]
            details["wav_bytes"] = len(converted_data)
            return PreparedAudio(
                data=converted_data,
                original_format="wav",
                content_type="audio/wav",
                converted=True,
                duration_seconds=new_info["duration_seconds"],
                sample_rate=new_info["sample_rate"],
                channels=new_info["channels"],
                details=details,
            )
        return PreparedAudio(
            data=data,
            original_format="wav",
            content_type="audio/wav",
            converted=False,
            duration_seconds=info["duration_seconds"],
            sample_rate=info["sample_rate"],
            channels=info["channels"],
            details=details,
        )

    if detected not in {"webm", "mp4", "ogg", "mp3", "aac", "flac"}:
        raise AudioError(
            "unsupported_audio",
            "Audio format samajh nahi aaya.",
            "WAV, MP3, OGG, M4A, AAC, FLAC ya browser recording (WebM) bhejein.",
            415,
        )

    converted = _convert_with_ffmpeg(data, detected)
    info = wav_info(converted)
    if info["duration_seconds"] and info["duration_seconds"] > 65:
        raise AudioError(
            "audio_too_long",
            "Recording bahut lambi hai (60 second se zyada).",
            f"Sirf {settings.max_record_seconds} second tak bolein.",
        )
    details["ffmpeg"] = find_ffmpeg()
    details["source_bytes"] = len(data)
    details["wav_bytes"] = len(converted)
    return PreparedAudio(
        data=converted,
        original_format=detected,
        content_type="audio/wav",
        converted=True,
        duration_seconds=info["duration_seconds"],
        sample_rate=info["sample_rate"],
        channels=info["channels"],
        details=details,
    )


def convert_wav_to_16k(data: bytes) -> bytes:
    """Used by check_gnani.py so users can test any local audio file."""
    prepared = prepare_for_stt(data)
    return prepared.data


def prepare_file_for_stt(path: str | Path) -> PreparedAudio:
    file_path = Path(path)
    if not file_path.is_file():
        raise AudioError("file_not_found", f"Audio file nahi mili: {file_path}")
    return prepare_for_stt(file_path.read_bytes(), filename=file_path.name)
