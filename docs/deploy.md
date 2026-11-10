# Deploying HisabSetu AI

The app is one Python process (FastAPI + uvicorn) with three runtime needs:
**Python**, **ffmpeg** (WebM/MP4 recordings → WAV before STT) and **a writable
place for the SQLite file**. No build step, no Node, no external database.

Three paths, in the order most people should try them:

| Path | Use it for | Cost | Persistence |
|---|---|---|---|
| **A. Local + screen recording** | the internship submission (the requirement is a *video* post) | free | local file |
| **B. Render (Docker, free plan)** | a public demo URL next to the post | free | ephemeral (`/tmp`), re-seeded on boot |
| **C. Fly.io (Docker + volume)** | a demo that keeps its data | ~free/cheap | persistent volume |

Everything below is verified except the two cloud uploads themselves: Docker is
not installed on this machine, so the container could not be built here. The
*command the container runs* was executed directly and checked — see
“What was verified” at the end.

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `GNANI_API_KEY` | yes, for voice | Never commit it. Set it in the host's dashboard. |
| `VOICE_KHATA_DB_URL` | recommended | SQLite URL, e.g. `sqlite:////data/khata.db`. The folder is created automatically. |
| `VOICE_KHATA_SEED` | optional | `1` (default) seeds the fictional demo ledger on first boot, `0` starts empty. |
| `GNANI_STT_LANGUAGE` / `GNANI_TTS_VOICE` | optional | Defaults `hi-IN` / `Nalini`. |
| `MAX_RECORD_SECONDS`, `MAX_TTS_CHARS`, `PENDING_TTL_MINUTES` | optional | Defaults 30 / 400 / 15. |
| `PORT` | platform-provided | The container binds `${PORT:-8000}`. |
| `GNANI_BASE_URL`, `GNANI_AUTH_HEADER`, `GNANI_AUTH_SCHEME` | optional | Only for a key issued for a different Gnani gateway. |

`.env` stays local and is in `.gitignore` / `.dockerignore`. On a host, put the
key in the platform's secret/environment settings, never in the repo.

---

## Path A — run locally and record the demo (recommended for the submission)

The challenge asks for a **video of your build posted publicly**; a hosted URL
is optional. This path has no security surface at all.

```powershell
cd <project folder>
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and check the Setup card shows Prisma **Live**,
Timbre **Live** and FFmpeg **Ready**.

Record with **Win + Alt + R** (Windows Game Bar) or OBS:

- 1280×720 or larger, browser zoom 110–125 % so Devanagari is readable.
- Show the mic actually being used, not only typing.
- Keep it to **60 seconds** if you want the “best 60-second demo” category.

The shot list lives in [linkedin-post.md](linkedin-post.md#60-second-video-shot-list).

---

## Path B — Render, free public demo (Docker)

1. **Push to GitHub** (the folder is not a git repository yet):

   ```bash
   git init
   git add .
   git commit -m "HisabSetu AI — voice-first khata with Gnani Prisma + Timbre"
   git branch -M main
   git remote add origin https://github.com/<you>/hisabsetu-ai.git
   git push -u origin main
   ```

   `.env`, `*.db`, `.venv/` and screenshots are already ignored, so the key and
   local data stay out of the repository.

2. **Render → New → Blueprint**, pick the repo. Render reads
   [render.yaml](../render.yaml): Docker runtime, free plan, Singapore region,
   health check `/api/health`.

3. When prompted for `GNANI_API_KEY`, paste the key. It is `sync: false`, i.e.
   stored only in Render's environment, never in the file.

4. Wait for the first deploy, then verify (replace the hostname):

   ```bash
   curl -s https://hisabsetu-ai.onrender.com/api/health
   curl -s -o /dev/null -w "%{http_code}\n" https://hisabsetu-ai.onrender.com/
   ```

   `/api/health` must show `"database": "ok"`, `"gnani": {"configured": true}`,
   and `"audio": {"ffmpeg_available": true}`. If `gnani.configured` is false the
   key did not reach the service — the app still serves the UI, but voice calls
   return `503 gnani_not_configured`.

5. Manual check in the browser: send a text command, confirm the preview, cancel
   it, then ask a balance question and press **Sunao** to hear the reply.

**Free-plan caveats, stated plainly:**

- The instance **sleeps** after ~15 minutes idle; the first request afterwards
  takes 30–60 s. Open the URL once before you record or post it.
- The filesystem is **ephemeral**: SQLite lives in `/tmp/khata.db` and resets on
  every restart/redeploy, re-seeding the fictional sample ledger. Fine for a
  demo, wrong for real bookkeeping.
- **The app is unauthenticated by design** (single shop, localhost). Anyone with
  the URL can add entries to the demo ledger. Use it only with fictional data,
  and take the service down (Render → Suspend) after the internship posts.
- Rotate the Gnani key afterwards if the URL was public for a while.

---

## Path C — Fly.io with a persistent volume

```bash
# once
fly auth login
fly launch --no-deploy            # accept the detected Dockerfile, pick a region
fly volumes create khata_data --size 1 --region bom
```

`fly.toml` needs the mount and the internal port:

```toml
[env]
  VOICE_KHATA_DB_URL = "sqlite:////data/khata.db"
  VOICE_KHATA_SEED = "1"

[[mounts]]
  source = "khata_data"
  destination = "/data"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0
```

Fly sets `PORT=8080` inside the machine; the container command already honours
`$PORT`. Then:

```bash
fly secrets set GNANI_API_KEY=...   # never in fly.toml
fly deploy
fly logs
curl -s https://<app>.fly.dev/api/health
```

This keeps the ledger across restarts because `/data` is a volume. Same warning
as Path B about the app being unauthenticated.

---

## Local Docker (if you have Docker Desktop)

```bash
docker build -t hisabsetu .
docker run --rm -p 8000:8000 --env-file .env -v hisabsetu-data:/data hisabsetu
curl -s http://127.0.0.1:8000/api/health
```

The image installs `ffmpeg` via apt, runs as a non-root user, and ships a
`HEALTHCHECK` against `/api/health`.

---

## Troubleshooting a deploy

| Symptom | Cause / fix |
|---|---|
| `503 gnani_not_configured` on `/api/tts` and `/api/stt` | `GNANI_API_KEY` not set in the host's environment (or the service was not restarted after adding it). `/api/health` shows `gnani.configured`. |
| Log says `unable to open database file` | The DB folder does not exist **and** is not writable. Use `sqlite:////data/khata.db` with a mounted volume, or `sqlite:////tmp/khata.db` on an ephemeral host. The app creates the folder itself when the parent is writable. |
| First request takes ~1 minute | Free-tier cold start. Open the URL before sharing it. |
| `ffmpeg_missing` when recording from the browser | The image installs ffmpeg; on a bare VM run `apt-get install -y ffmpeg`, or rely on the bundled `imageio-ffmpeg` wheel already in `requirements.txt`. |
| Data disappeared after redeploy | Expected on ephemeral filesystems (Path B). Use a volume (Path C) or a real database. |
| Health check failing but the app works locally | The host expects the app on `$PORT` — keep the `--port ${PORT:-8000}` command, or set the service's internal port to 8000. |

---

## What was verified here

- Production-style start without Docker:
  `VOICE_KHATA_DB_URL=sqlite:///./deploy_sim/data/khata.db uvicorn main:app --host 0.0.0.0 --port 8082`
  → `database ok`, `ffmpeg_available true`, 8 seeded customers, DB file created in
  a folder that did not exist (the new `database._ensure_sqlite_directory` helper,
  covered by `tests/test_database.py`).
- Full suite: **434 passed**.
- Live Gnani: one TTS and one STT request succeeded (documented in
  [fix-report.md](fix-report.md)).
- **Not verified:** the Docker build and the Render/Fly deploys themselves —
  Docker is not installed on this machine. The files are standard
  Dockerfile/blueprint formats; run the commands above to confirm on your host.
