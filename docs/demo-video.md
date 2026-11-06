# Demo video — what it shows, how it was made, what is real

Two cuts, both recorded from the running app at `http://127.0.0.1:8000` with the
demo database:

| File | Length | Content |
|---|---|---|
| `demo/hisabsetu-demo-voice.mp4` | 68.7 s | all seven beats, including the transcript-correction beat |
| `demo/hisabsetu-demo-60s.mp4` | 60.8 s | same cut without the correction beat, for the "best 60-second demo" category |

1920×1080, 30 fps, H.264 + AAC, burned-in captions, Hindi voice-over.

The voice is **Gnani Timbre v2.5 · Deepak** (Hindi, male, speed 1.0). The
narration opens presenter-style — *"Jai Hind doston! Pichhle kuch hafton se main
is par kaam kar raha hoon…"* — instead of the old third-person hook. Voice
samples for other Timbre voices live in `demo/audio/samples/`; regenerate the
narration with any of them using the env vars below.

## Beat list (matches [demo-script.md](demo-script.md))

| Time | On screen | Beat |
|---|---|---|
| 0:00 | dashboard, ₹4,600 outstanding | "Jai Hind doston! … ek khata, jo sirf bolne se chalta hai" |
| 0:03 | mic card | the mic is tapped, the command is spoken |
| 0:08 | transcript + preview | ₹150 credit for Ramesh, ₹450 → ₹600, "Ledger abhi nahi badla hai" |
| 0:17 | success card, dashboard ₹4,750 | Confirm is pressed — now it saves |
| 0:29 | balance card | "Ramesh ji ka ₹600 baaki hai", spoken by Timbre |
| 0:40 | "2 kaam ek saath" card | a two-instruction sentence is refused, both clauses listed |
| 0:54 | rebuilt preview ₹250 | "Transcript sudharein" fixes the amount instead of the database |
| 1:03 | history, 14 entries | nothing moves without Confirm |

(The 60 s cut drops the correction beat, so the close lands at 1:00.)

## How it was recorded

1. `demo/tts_assets.py` synthesizes the narration and the three spoken commands
   with **Gnani Timbre** through the app's own `/api/tts`.
2. `demo/capture.mjs` launches headless Edge with
   `--use-file-for-fake-audio-capture=<wav>`, so the browser's MediaRecorder
   records that WAV as its microphone input. The audio really goes through
   `POST /api/stt` → FFmpeg → **Gnani Prisma** → `parser.py`; nothing about the
   transcript or the preview is mocked. The script also captures the actual
   `/api/tts` response bytes the app played when **Sunao** was pressed.
3. `demo/assemble.py` turns the screencast frames into 30 fps clips, places the
   narration, the command audio and the TTS reply on the timeline at their
   recorded event times, and muxes the final MP4.

Rebuild everything:

```powershell
# voice assets (defaults come from .env; cached after the first run)
python demo/tts_assets.py
# a different Timbre voice:
#   TTS_MODEL=timbre-v3.0 TTS_VOICE=Tarika TTS_SPEED=1.15 VOICE_DIR_NAME=voice-tarika python demo/tts_assets.py
AUDIO_DIR=demo/audio/voice-deepak node demo/capture.mjs   # records the six segments (~2 min, 4 real STT calls)
VOICE_DIR=demo/audio/voice-deepak NARRATION_TEMPO=1.0 python demo/assemble.py   # full cut
CUT=60 VOICE_DIR=demo/audio/voice-deepak NARRATION_TEMPO=1.0 python demo/assemble.py   # 60 s cut
# silent masters are the same files with the audio track stripped:
ffmpeg -i demo/hisabsetu-demo-voice.mp4 -an -c:v copy demo/hisabsetu-demo-silent.mp4
```

Reset the demo ledger between takes (the confirm in the video is a real write):

```powershell
# server stopped, then:
Copy-Item demo_run/khata.pristine.db demo_run/khata.db
```

## What is real, and what is staged

- **Real:** the ledger, the amounts, the parsing, the confirmation, the SQLite
  commit, the Prisma transcription of the audio it was given, and the Timbre WAV
  played by the app. The numbers on screen come from the database — ₹4,600 →
  ₹4,750, Ramesh ₹450 → ₹600.
- **Staged:** the *voice*. The commands are spoken by Timbre (synthesized), not
  by a human, and fed in through the browser's fake-capture device. The narration
  is Timbre as well. Recording conditions are therefore studio-clean: do **not**
  present this as proof of noisy-shop accuracy. That tier is still unmeasured
  (see [noisy-audio-eval.md](noisy-audio-eval.md)).
- **Edited:** the video is cut together from six takes, so jump cuts between
  beats are expected. No state was faked inside a take.

To record it in your own voice instead, keep `demo/capture.mjs` but drop the
fake-audio flags and speak the three command lines live; everything else
(narration timing, captions, assembly) stays the same.

## Publishing

The post text is in [linkedin-post.md](linkedin-post.md). Upload the MP4 directly
to LinkedIn (native video), keep the captions on screen — most of the feed
watches muted.
