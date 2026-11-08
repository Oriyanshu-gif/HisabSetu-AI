"""Audio validation and genuine WebM -> WAV conversion tests."""

from __future__ import annotations

import struct
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

import audio_utils
from audio_utils import AudioError, find_ffmpeg, prepare_for_stt, sniff_format, wav_info
from conftest import make_wav


def wav_params(data: bytes) -> tuple[int, int, int]:
    """Return (channels, sample_rate, bits_per_sample) from a PCM WAV header."""
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    channels = struct.unpack("<H", data[22:24])[0]
    rate = struct.unpack("<I", data[24:28])[0]
    bits = struct.unpack("<H", data[34:36])[0]
    return channels, rate, bits


def encode_webm(wav_bytes: bytes) -> bytes:
    exe = find_ffmpeg()
    if not exe:
        pytest.skip("FFmpeg is not available on this machine")
    with tempfile.TemporaryDirectory(prefix="vk_webm_") as tmp:
        source = Path(tmp) / "in.wav"
        target = Path(tmp) / "out.webm"
        source.write_bytes(wav_bytes)
        completed = subprocess.run(
            [exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
             "-c:a", "libopus", "-b:a", "24k", str(target)],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            pytest.skip(f"FFmpeg build cannot encode Opus: {completed.stderr[-120:]!r}")
        return target.read_bytes()


def test_sniff_wav():
    assert sniff_format(make_wav(0.1)) == "wav"


def test_sniff_other_containers():
    assert sniff_format(b"OggS" + b"\x00" * 30) == "ogg"
    assert sniff_format(b"\x1aE\xdf\xa3" + b"\x00" * 30) == "webm"
    assert sniff_format(b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 20) == "mp4"
    assert sniff_format(b"ID3" + b"\x00" * 30) == "mp3"
    assert sniff_format(b"fLaC" + b"\x00" * 30) == "flac"


def test_sniff_unknown_returns_none():
    assert sniff_format(b"not audio at all") is None
    assert sniff_format(b"") is None


def test_empty_upload_is_rejected():
    with pytest.raises(AudioError) as error:
        prepare_for_stt(b"", "audio/webm", "voice.webm")
    assert error.value.code == "empty_audio"
    assert error.value.status_code == 422


def test_garbage_upload_is_rejected():
    with pytest.raises(AudioError) as error:
        prepare_for_stt(b"hello world, definitely not audio" * 4, "application/octet-stream", "x.bin")
    assert error.value.code == "unsupported_audio"
    assert error.value.status_code == 415


def test_wav_passes_through_without_conversion():
    raw = make_wav(1.0, rate=16000)
    prepared = prepare_for_stt(raw, "audio/wav", "voice.wav")
    assert prepared.converted is False
    assert prepared.original_format == "wav"
    assert prepared.sample_rate == 16000
    assert prepared.channels == 1
    assert 0.9 <= prepared.duration_seconds <= 1.1
    assert prepared.data == raw


def test_stereo_44k_wav_is_accepted_directly():
    raw = make_wav(0.5, rate=44100, channels=2)
    prepared = prepare_for_stt(raw, "audio/wav", "voice.wav")
    assert prepared.converted is False
    assert prepared.sample_rate == 44100
    assert prepared.channels == 2


def test_48k_wav_is_resampled_for_prisma():
    if not find_ffmpeg():
        pytest.skip("FFmpeg is not available on this machine")
    raw = make_wav(0.4, rate=48000)
    prepared = prepare_for_stt(raw, "audio/wav", "timbre.wav")
    assert prepared.converted is True
    assert prepared.original_format == "wav"
    channels, rate, bits = wav_params(prepared.data)
    assert (channels, rate, bits) == (1, 16000, 16)


def test_out_of_range_wav_without_ffmpeg_is_actionable(monkeypatch):
    monkeypatch.setattr(audio_utils, "find_ffmpeg", lambda: None)
    with pytest.raises(AudioError) as error:
        prepare_for_stt(make_wav(0.3, rate=48000), "audio/wav", "timbre.wav")
    assert error.value.code == "wav_needs_conversion"
    assert error.value.status_code == 503


def test_wav_over_one_minute_is_rejected():
    raw = make_wav(66.0, rate=16000)
    with pytest.raises(AudioError) as error:
        prepare_for_stt(raw, "audio/wav", "long.wav")
    assert error.value.code == "audio_too_long"


def test_upload_size_limit(monkeypatch):
    monkeypatch.setattr(audio_utils, "settings", replace(audio_utils.settings, max_audio_bytes=100))
    with pytest.raises(AudioError) as error:
        prepare_for_stt(make_wav(1.0), "audio/wav", "voice.wav")
    assert error.value.code == "audio_too_large"
    assert error.value.status_code == 413


def test_corrupt_wav_header_is_rejected():
    broken = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"garbage" * 20
    with pytest.raises(AudioError) as error:
        prepare_for_stt(broken, "audio/wav", "voice.wav")
    assert error.value.code == "invalid_wav"


def test_wav_info_reads_header():
    info = wav_info(make_wav(2.0, rate=8000))
    assert info["sample_rate"] == 8000
    assert info["channels"] == 1
    assert info["sample_width"] == 2
    assert 1.9 <= info["duration_seconds"] <= 2.1


def test_webm_is_really_converted_to_wav():
    """Encode a real WebM/Opus file, then assert a 16 kHz mono PCM WAV comes out."""
    webm = encode_webm(make_wav(1.2, rate=44100, channels=2))
    assert sniff_format(webm) == "webm"
    assert not webm.startswith(b"RIFF")

    prepared = prepare_for_stt(webm, "audio/webm", "voice.webm")
    assert prepared.converted is True
    assert prepared.original_format == "webm"
    assert prepared.content_type == "audio/wav"
    channels, rate, bits = wav_params(prepared.data)
    assert (channels, rate, bits) == (1, 16000, 16)
    assert prepared.data != webm
    assert 0.9 <= prepared.duration_seconds <= 1.6
    assert prepared.details["wav_bytes"] > 1000


def test_ffmpeg_missing_error_is_actionable(monkeypatch):
    monkeypatch.setattr(audio_utils, "find_ffmpeg", lambda: None)
    fake_webm = b"\x1aE\xdf\xa3" + b"\x00" * 400
    with pytest.raises(AudioError) as error:
        prepare_for_stt(fake_webm, "audio/webm", "voice.webm")
    assert error.value.code == "ffmpeg_missing"
    assert error.value.status_code == 503
    assert "FFmpeg" in error.value.hint
