"""Real Gnani connectivity check. Makes live API calls (small cost).

Examples (PowerShell, with the virtualenv active):

    python check_gnani.py --tts "नमस्ते, वॉइस खाता ए आई में आपका स्वागत है।"
    python check_gnani.py --audio samples\\udhaar.wav
    python check_gnani.py --roundtrip

``--roundtrip`` synthesizes a Hindi sentence with Timbre and feeds that audio
back into Prisma STT, so both services are exercised without a recording.
Nothing is written to the ledger. The API key is never printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audio_utils import AudioError, find_ffmpeg, prepare_file_for_stt, prepare_for_stt
from config import settings
from gnani_client import GnaniError, is_configured, synthesize, transcribe

DEFAULT_TTS_TEXT = "रमेश जी का एक सौ पचास रुपये का उधार लिख दिया गया है। अब बकाया चार सौ पचास रुपये है।"


def print_config() -> None:
    print("HisabSetu AI — Gnani connectivity check")
    print(f"  base URL       : {settings.gnani_base_url}")
    print(f"  auth header    : {settings.gnani_auth_header}")
    print(f"  STT endpoint   : {settings.stt_url}")
    print(f"  STT language   : {settings.gnani_stt_language}")
    print(f"  TTS endpoint   : {settings.tts_url}")
    print(f"  TTS model/voice: {settings.gnani_tts_model} / {settings.gnani_tts_voice}")
    print(f"  API key        : {'set (hidden)' if is_configured() else 'MISSING'}")
    print(f"  FFmpeg         : {find_ffmpeg() or 'not found'}")
    print()


def run_tts(text: str, output: Path) -> bytes:
    print(f"TTS request: {len(text)} characters -> {settings.gnani_tts_voice}")
    result = synthesize(text)
    output.write_bytes(result.audio)
    print(f"  OK: {len(result.audio)} bytes, content-type={result.content_type}")
    print(f"  Saved: {output.resolve()}")
    return result.audio


def run_stt(audio_path: Path) -> str:
    print(f"STT request: {audio_path}")
    prepared = prepare_file_for_stt(audio_path)
    print(
        f"  audio: format={prepared.original_format} converted={prepared.converted} "
        f"duration={prepared.duration_seconds}s rate={prepared.sample_rate} Hz"
    )
    result = transcribe(prepared.data)
    print(f"  OK: transcript={result.transcript!r}")
    print(f"  request_id={result.request_id} model={result.model}")
    return result.transcript


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check real Gnani Prisma STT / Timbre TTS connectivity")
    parser.add_argument("--audio", type=Path, help="local audio file for STT (wav/mp3/ogg/m4a/webm)")
    parser.add_argument("--tts", nargs="?", const=DEFAULT_TTS_TEXT, help="text to synthesize")
    parser.add_argument("--out", type=Path, default=Path("gnani_tts_check.wav"), help="TTS output path")
    parser.add_argument("--roundtrip", action="store_true", help="TTS then STT on the generated audio")
    args = parser.parse_args(argv)

    print_config()

    if not is_configured():
        print("SKIPPED: GNANI_API_KEY is not configured.")
        print("  1. Copy .env.example to .env")
        print("  2. Put your real key in GNANI_API_KEY")
        print("  3. Restart the terminal and run this script again.")
        return 2

    did_something = False
    tts_audio: bytes | None = None

    if args.tts is not None or args.roundtrip:
        try:
            tts_audio = run_tts(args.tts or DEFAULT_TTS_TEXT, args.out)
            did_something = True
        except GnaniError as exc:
            print(f"TTS FAILED [{exc.code}] {exc.message}")
            if exc.hint:
                print(f"  hint: {exc.hint}")
            return 1

    if args.audio is not None:
        try:
            run_stt(args.audio)
            did_something = True
        except (GnaniError, AudioError) as exc:
            print(f"STT FAILED [{exc.code}] {exc.message}")
            print(f"  hint: {exc.hint}")
            return 1

    if args.roundtrip:
        try:
            assert tts_audio is not None
            prepared = prepare_for_stt(tts_audio, filename="roundtrip.wav")
            result = transcribe(prepared.data)
            print(f"Round-trip STT: {result.transcript!r}")
            did_something = True
        except (GnaniError, AudioError) as exc:
            print(f"ROUND-TRIP FAILED [{exc.code}] {exc.message}")
            print(f"  hint: {exc.hint}")
            return 1

    if not did_something:
        print("No action requested. Use --audio PATH, --tts \"...\" or --roundtrip.")
        return 0

    print("\nAll requested Gnani calls succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
