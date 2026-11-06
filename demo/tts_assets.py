"""Generate the demo video's audio assets with Gnani Timbre.

The voice is configurable so the same script can render the narration in a
different Timbre model/voice:

    TTS_MODEL=timbre-v3.0 TTS_VOICE=Shivani TTS_SPEED=1.15 VOICE_DIR_NAME=voice-v3 \
        python demo/tts_assets.py

Writes 48 kHz mono 16-bit WAVs and prints their durations. Existing files are
reused, so re-running is free.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # allow `python demo/tts_assets.py`
    sys.path.insert(0, str(ROOT))

import gnani_client  # noqa: E402
from config import settings  # noqa: E402
MODEL = os.environ.get("TTS_MODEL", settings.gnani_tts_model)
VOICE = os.environ.get("TTS_VOICE", settings.gnani_tts_voice)
SPEED = float(os.environ.get("TTS_SPEED", str(settings.gnani_tts_speed)) or 1.0)
OUT = ROOT / "demo" / "audio" / os.environ.get("VOICE_DIR_NAME", "voice")
FFMPEG = ROOT / ".venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"

# Command phrases: spoken into the real microphone path (fake-capture device).
COMMANDS = {
    "cmd1": "रमेश को डेढ़ सौ रुपये का उधार लिख दो।",
    "cmd2": "रमेश का कितना उधार बाकी है?",
    "cmd3": "रमेश को दो सौ उधार और सुनीता ने दो सौ जमा किए।",
}

# Narration: Hinglish script rendered in Devanagari so the Hindi voice reads it naturally.
NARRATION = {
    "n1": "जय हिंद दोस्तों! पिछले कुछ हफ़्तों से मैं इस पर काम कर रहा हूँ — एक खाता, जो सिर्फ़ बोलने से चलता है।",
    "n2": "ये है हिसाबसेतु ए आई। मैं सिर्फ़ बोलूँगा।",
    "n3": "प्रिस्मा ने सुना, पार्सर ने डेढ़ सौ का उधार बना दिया — रमेश चार सौ पचास से छह सौ। और सबसे ज़रूरी बात: लेजर अभी नहीं बदला।",
    "n4": "कन्फ़र्म दबाया — अब सेव हुआ। कुल चार हज़ार सात सौ पचास।",
    "n5": "बकाया पूछा — जवाब आया, और टिम्ब्रे ने उसे हिंदी में बोलकर सुनाया।",
    "n6": "एक सांस में दो हुक्म? ये मना कर देता है, दोनों दिखाता है, अलग-अलग करने को कहता है।",
    "n7": "ग़लत सुना हो, तो मैं ट्रांसक्रिप्ट सुधारता हूँ — डेटाबेस नहीं।",
    "n8": "बिना कन्फ़र्म कुछ नहीं बदलता। यही इस ऐप का पूरा आइडिया है।",
}


def synthesize(text: str) -> bytes:
    original = gnani_client.settings
    gnani_client.settings = replace(
        original, gnani_tts_model=MODEL, gnani_tts_voice=VOICE, gnani_tts_speed=SPEED
    )
    try:
        return gnani_client.synthesize(text).audio
    finally:
        gnani_client.settings = original


def duration(path: Path) -> float:
    out = subprocess.run(
        [str(FFMPEG), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, errors="ignore",
    ).stderr
    for line in out.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            hours, minutes, seconds = stamp.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return 0.0


def fetch(name: str, text: str) -> Path:
    wav = OUT / f"{name}.wav"
    if wav.exists():
        print(f"  {name}: cached {duration(wav):.2f}s")
        return wav
    for attempt in range(1, 5):
        try:
            audio = synthesize(text)
            if not audio.startswith(b"RIFF"):
                raise RuntimeError(f"non-WAV body {audio[:80]!r}")
            wav.write_bytes(audio)
            print(f"  {name}: generated {duration(wav):.2f}s")
            return wav
        except Exception as error:  # noqa: BLE001 - provider hiccups
            print(f"  {name}: attempt {attempt} {type(error).__name__}: {error}")
            time.sleep(3 * attempt)
    raise SystemExit(f"TTS failed for {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"model={MODEL} voice={VOICE} speed={SPEED} -> {OUT.relative_to(ROOT)}")
    total = 0.0
    for name, text in {**COMMANDS, **NARRATION}.items():
        total += duration(fetch(name, text))
    print(f"total audio: {total:.1f}s")


if __name__ == "__main__":
    main()
