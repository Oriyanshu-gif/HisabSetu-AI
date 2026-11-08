# Deploy on Vercel (instead of Render)

The repository ships everything Vercel needs:

| File | What it does |
|---|---|
| `api/index.py` | Serverless entry point; exports the FastAPI `app` |
| `vercel.json` | Sends every path (`/`, `/static/...`, `/api/...`) to that function and enables file tracing for `static/`, `templates/` |
| `.vercelignore` | Keeps `.venv`, demo videos, cached audio and local databases out of the upload |

Vercel does not run Docker and does not give you a disk, so two things change
compared with the Render/Fly setups: **the database** and **ffmpeg**.

## 1. Deploy

```bash
npm i -g vercel          # once
vercel login
vercel link              # creates the project, links this folder
vercel --prod
```

Then add the secrets (dashboard → Project → Settings → Environment Variables, or
the CLI). Never paste the key into a file that gets committed:

```bash
vercel env add GNANI_API_KEY production
vercel env add VOICE_KHATA_SEED production      # "1"
vercel env add GNANI_TTS_VOICE production       # "Nalini"
vercel env add MAX_RECORD_SECONDS production    # "20"
vercel env add MAX_AUDIO_BYTES production       # "4000000"
vercel --prod                                   # redeploy so they apply
```

`MAX_AUDIO_BYTES` matters: Vercel rejects request bodies above ~4.5 MB, so the
upload limit is lowered to 4 MB and recordings are capped at 20 seconds.

## 2. The database (pick one)

### Option A — demo, no persistence

```bash
vercel env add VOICE_KHATA_DB_URL production    # sqlite:////tmp/khata.db
```

`/tmp` is the only writable path in a serverless function. It works (sample data
is re-seeded on a cold start) but it is **per instance and temporary**: two
concurrent lambdas have separate ledgers and everything is lost on redeploy.
Fine for a link you send a reviewer; not a real shop account.

### Option B — persistent Postgres (recommended)

1. Vercel dashboard → Storage → Marketplace → create a Postgres (Neon) database
   and connect it to the project.
2. Set the connection string, using the psycopg 3 driver name:

```bash
vercel env add VOICE_KHATA_DB_URL production
# postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
```

`psycopg[binary]` is already in `requirements.txt`, so SQLAlchemy can open that
URL. `database.py` only creates a folder for `sqlite://` URLs; any other URL is
passed to SQLAlchemy unchanged, and the tables are created on the first request.

## 3. ffmpeg and audio uploads

Browser recordings arrive as WebM/MP4 and are converted to 16 kHz mono WAV
before STT. `requirements.txt` includes `imageio-ffmpeg`, whose Linux wheel
carries a static ffmpeg binary, so conversion usually works on Vercel too. Check
it on the deployed URL:

```bash
curl -s https://<your-app>.vercel.app/api/health
# {"status":"ok", ..., "ffmpeg": true}
```

If `ffmpeg` is `false`, voice uploads return a clear `ffmpeg_missing` error while
the text workflow keeps working. In that case set `FFMPEG_PATH` to a binary you
ship yourself, or use the Docker deployment in `docs/deploy.md`.

## 4. Limits to keep in mind

- **60 s per request** (`maxDuration` in `vercel.json`). One STT or TTS call is a
  few seconds, so a normal command fits; a batch of very long clips would not.
- **Cold starts**: the first request after idle is slower (2–5 s).
- **No authentication**: this build has no login. A public Vercel URL lets anyone
  write to your ledger — use it as a demo, or put Vercel Authentication / a
  password proxy in front of it before sharing widely.
- Pending confirmations are stored in the database, so they survive between
  requests only with Option B (Postgres).

## 5. Verify after deploying

```bash
curl -s https://<your-app>.vercel.app/api/health
curl -s https://<your-app>.vercel.app/api/languages
curl -s -X POST https://<your-app>.vercel.app/api/command \
  -H 'content-type: application/json' \
  -d '{"text":"Ramesh 150 udhaar","language":"hi-IN"}'
```

The third call must return a `proposal` **without** writing anything; the ledger
only changes after `POST /api/pending/{id}/confirm`.
