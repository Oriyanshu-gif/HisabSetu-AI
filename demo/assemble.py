"""Assemble the demo video from the captured segments.

video  : demo/raw/<segment>/frames/*.jpg  (timing from frames.json)
audio  : narration (n1..n8, sped up 8%), the exact command WAVs fed to the
         microphone, and the real /api/tts bytes the app played back.
output : demo/hisabsetu-demo-<cut>.mp4
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "demo" / "raw"
VOICE = ROOT / os.environ.get("VOICE_DIR", "demo/audio/voice")
WORK = RAW / "build"
OUT = ROOT / "demo"

FFMPEG = ROOT / ".venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
NARRATION_TEMPO = float(os.environ.get("NARRATION_TEMPO", "1.08") or 1.08)
FPS = 30

# segment order and which audio lands where (times are event names or seconds)
SEGMENTS = ["s1-dashboard", "s2-voice-credit", "s3-balance", "s4-compound", "s5-correction", "s6-close"]
# CUT=60 drops the correction beat so the whole thing lands just under a minute.
CUT = int(os.environ.get("CUT", "0") or 0)
# MODE=silent stops after the picture, so the AI voiceover is a separate stage.
MODE = os.environ.get("MODE", "voice").strip().lower()

# (file stem, anchor event or fixed offset in seconds, extra delay)
TRACK = {
    "s1-dashboard": [("n1", "start", 0.25)],
    "s2-voice-credit": [
        ("n2", "start", 0.2),
        ("cmd1", "mic_press", -0.15),
        ("n3", "caption_n3", 0.15),
        ("n4", "caption_n4", 0.15),
    ],
    "s3-balance": [
        ("cmd2", "mic_press", -0.15),
        ("n5", "caption_n5", 0.15),
    ],
    "s4-compound": [
        ("cmd3", "mic_press", -0.15),
        ("n6", "caption_n6", 0.15),
    ],
    "s5-correction": [("n7", "caption_n7", 0.15)],
    "s6-close": [("n8", "caption_n8", 0.2)],
}


def ffmpeg(args: list[str], label: str = "") -> None:
    result = subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", *args],
                            capture_output=True, text=True, errors="ignore")
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed ({label}):\n{result.stderr[-3000:]}")


def duration(path: Path) -> float:
    out = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True, errors="ignore").stderr
    for line in out.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def timeline(segment: str) -> tuple[list[dict], dict]:
    frames = json.loads((RAW / segment / "frames.json").read_text())["frames"]
    events = json.loads((RAW / segment / "events.json").read_text())
    return frames, events


def encode_segment(segment: str, index: int) -> tuple[Path, float, dict]:
    frames, events = timeline(segment)
    end_time = next((e["t"] for e in events["events"] if e["name"] == "end"), frames[-1]["t"] + 0.5)
    # monotonic, minimum one frame step
    clean: list[dict] = []
    last = -1.0
    for frame in frames:
        t = max(frame["t"], last + 1.0 / FPS)
        clean.append({"file": frame["file"], "t": t})
        last = t

    lines = ["ffconcat version 1.0"]
    for i, frame in enumerate(clean):
        nxt = clean[i + 1]["t"] if i + 1 < len(clean) else end_time
        hold = max(1.0 / FPS, nxt - frame["t"])
        path = (RAW / segment / "frames" / frame["file"]).as_posix()
        lines.append(f"file '{path}'")
        lines.append(f"duration {hold:.4f}")
    # concat demuxer needs the final image repeated
    lines.append(f"file '{(RAW / segment / 'frames' / clean[-1]['file']).as_posix()}'")

    listfile = WORK / f"{segment}.txt"
    listfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = WORK / f"{index:02d}-{segment}.mp4"
    ffmpeg([
        "-f", "concat", "-safe", "0", "-i", str(listfile),
        "-vf", f"fps={FPS},scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-g", "60",
        "-pix_fmt", "yuv420p", "-color_range", "tv",
        "-t", f"{end_time:.3f}", "-y", str(out),
    ], label=segment)
    return out, end_time, events


def event_map(events: dict) -> dict[str, float]:
    table: dict[str, float] = {"start": 0.0}
    for item in events["events"]:
        table.setdefault(item["name"], item["t"])
    return table


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    segments = [s for s in SEGMENTS if not (CUT and s == "s5-correction")]
    clips: list[Path] = []
    offsets: dict[str, float] = {}
    cursor = 0.0
    for index, segment in enumerate(segments):
        clip, length, events = encode_segment(segment, index)
        offsets[segment] = cursor
        cursor += length
        clips.append(clip)
        print(f"{segment}: {length:.2f}s (total {cursor:.2f}s)")

    concat_list = WORK / "video.txt"
    concat_list.write_text("\n".join(f"file '{c.as_posix()}'" for c in clips) + "\n", encoding="utf-8")
    video = WORK / "video-silent.mp4"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", "-y", str(video)], "concat")

    if MODE == "silent":
        target = OUT / ("hisabsetu-demo-silent-60s.mp4" if CUT else "hisabsetu-demo-silent.mp4")
        ffmpeg(["-i", str(video), "-c", "copy", "-movflags", "+faststart", "-y", str(target)], "silent")
        print(f"wrote {target.relative_to(ROOT)}  {target.stat().st_size / 1048576:.1f} MB  {duration(target):.2f}s")
        (WORK / "video-silent.mp4").unlink(missing_ok=True)
        return

    # ---- audio: the AI voiceover is laid over the finished picture ----
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    total = duration(video)
    for segment in segments:
        events = json.loads((RAW / segment / "events.json").read_text())
        table = event_map(events)
        base = offsets[segment]
        for stem, anchor, shift in TRACK.get(segment, []):
            if stem.startswith("cmd"):
                source = VOICE / f"{stem}.wav"
                tempo = None
            elif stem.startswith("tts_"):
                source = RAW / segment / f"{stem}.wav"
                tempo = None
            else:
                source = VOICE / f"{stem}.wav"
                tempo = NARRATION_TEMPO
            if not source.exists():
                print(f"  ! missing audio {source.name}")
                continue
            when = (table.get(anchor, 0.0) if anchor != "start" else 0.0) + shift
            at = max(0.0, base + when)
            idx = len(inputs) // 2  # inputs is a flat ["-i", path, ...] list
            inputs.extend(["-i", str(source)])
            chain = f"[{idx}:a]"
            if tempo:
                chain += f"atempo={tempo},"
            else:
                chain += ""
            chain += f"adelay={int(at * 1000)}|{int(at * 1000)},apad=whole_dur={total:.3f}[a{idx}]"
            filters.append(chain)
            labels.append(f"[a{idx}]")

    mixed = WORK / "mix.wav"
    graph = ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0," \
                     f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.25,afade=t=out:st={max(0, total - 0.9):.2f}:d=0.9[out]"
    ffmpeg([*inputs, "-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-y", str(mixed)], "mix")

    name = "hisabsetu-demo-60s.mp4" if CUT else "hisabsetu-demo-voice.mp4"
    for name, cut in ((name, None),):
        target = OUT / name
        ffmpeg([
            "-i", str(video), "-i", str(mixed),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", "-y", str(target),
        ], name)
        print(f"wrote {target.relative_to(ROOT)}  {target.stat().st_size / 1048576:.1f} MB  {duration(target):.2f}s")

    (WORK / "video-silent.mp4").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
