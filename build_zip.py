"""Package project sources for sharing. Excludes secrets, runtime junk and the local DB."""
from __future__ import annotations

import zipfile
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "voice-khata-ai-latest.zip"

# Skipped at any depth: caches, virtualenvs, build output.
EXCLUDE_ANYWHERE = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    "venv",
    ".venv",
    "dist",
    "build",
}
# Skipped only at the project root, so docs/screenshots still ships.
EXCLUDE_TOP_LEVEL_DIRS = {
    # agent / chat workspace data
    ".cloud-attachments",
    ".freebuff",
    # stale snapshots of files that also live in the tree
    ".backup",
    # local runtime data (regenerate with VOICE_KHATA_SEED=1)
    "demo_run",
    # old screenshots; the ones used in docs/ live in docs/screenshots
    "screenshots",
    # browser profiles and frame dumps from the video recording runs
    ".tmp-demo",
    ".tmp-rec",
}
# Skipped as a path prefix, for bulky folders inside an otherwise shipped directory.
EXCLUDE_NESTED_DIRS = {
    "demo/raw",              # extracted capture frames, regenerate with demo/capture.mjs
    "demo/raw-en",
    "demo/raw-hi",
    "demo/audio",            # narration wavs, regenerate with demo/tts_assets.py
}
EXCLUDE_FILES = {
    ".env",                        # holds the live GNANI_API_KEY
    "voice_khata.db",              # local demo data, regenerate with VOICE_KHATA_SEED=1
    "voice-khata-ai-latest.zip",
    "voice_khata_ai.zip",
    "survey_row_buf",
}
# Name patterns for one-off probes, logs, installers and screenshot scratch files.
EXCLUDE_PATTERNS = (
    "*.log",
    "*.pid",
    "poetry.lock.tmp",
    "python-3*.exe",
    "freebuff_screenshot*.png",
    "screenshot_*.png",
    "before_server.png",
    "parser_*.txt",
    "parser_*.json",
    "compound_resp.json",
    "p_out.txt",
    "verified_parsed.txt",
    "live_known_cases.txt",
    "sweep_*.txt",
    "tmp_log.txt",
    "report.csv",
    "gnani_conn_check.txt",
    "gnani_tts_probe.txt",
    "gnani_tts_raw.txt",
    "gnani_tts_check.wav",
    "gnani_tts_live.wav",
)
# Recordings are their own deliverables (5 MB+), keep them out of the source bundle.
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".mp4", ".webm", ".mov", ".wav"}


def is_excluded(path: Path, rel: Path) -> bool:
    parents = rel.parts[:-1]
    if any(part in EXCLUDE_ANYWHERE for part in parents):
        return True
    posix = rel.as_posix()
    if any(posix == prefix or posix.startswith(prefix + "/") for prefix in EXCLUDE_NESTED_DIRS):
        return True
    # Any future capture dump (demo/raw-*) is bulk by definition.
    if posix.startswith("demo/raw-"):
        return True
    # Any scratch folder (.tmp-demo, .tmp-rec, .tmp-en …) is local-only.
    if any(part.startswith(".tmp") for part in rel.parts):
        return True
    if parents and parents[0] in EXCLUDE_TOP_LEVEL_DIRS:
        return True
    if path.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES:
        return True
    return any(fnmatch(path.name, pattern) for pattern in EXCLUDE_PATTERNS)


def build() -> None:
    kept = 0
    skipped = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            rel = path.relative_to(ROOT)
            if is_excluded(path, rel):
                skipped += 1
                continue
            # broken symlinks and vanished temp files raise here; skip instead of failing
            try:
                if not path.is_file():
                    continue
            except OSError:
                skipped += 1
                continue
            zf.write(path, rel.as_posix())
            kept += 1

    with zipfile.ZipFile(OUT) as zf:
        names = zf.namelist()
        checks = {
            "contains .env": any(n == ".env" or n.endswith("/.env") for n in names),
            "contains any .db": any(n.endswith(".db") for n in names),
            "contains chat workspace": any(n.startswith((".cloud-attachments/", ".freebuff/")) for n in names),
            "contains recordings": any(n.endswith((".mp4", ".webm")) for n in names),
            "has PWA service worker": "static/sw.js" in names,
            "has PWA manifest": "static/manifest.webmanifest" in names,
            "has a PWA icon": any(n.startswith("static/icons/") for n in names),
            "has LinkedIn screenshots": sum(n.startswith("docs/screenshots/") for n in names),
            "has demo script": "docs/demo-script.md" in names,
            "has .env.example": ".env.example" in names,
        }
    print(f"zip: {OUT.name}")
    print(f"files: {kept} (skipped {skipped} ignored entries)")
    print(f"bytes: {OUT.stat().st_size}")
    for label, value in checks.items():
        print(f"{label}: {value}")


if __name__ == "__main__":
    build()
