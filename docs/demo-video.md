# Demo video — what it shows, how it was made, what is real

Recorded from the running app at `http://127.0.0.1:8000` with the demo database,
in the three-section layout (Bolo / Grahak / Hisaab):

| File | Length | Language | Content |
|---|---|---|---|
| `demo/hisabsetu-demo-60s.mp4` | 62.4 s | Hindi voice-over, Hinglish captions | same cut without the correction beat, for the "best 60-second demo" category |
| `demo/hisabsetu-demo-60s-en.mp4` | 60.1 s | English voice-over, English captions | identical picture timeline, narrated in English |
| `demo/hisabsetu-demo-60s-prev.mp4` | 61.2 s | Hindi | the earlier take, recorded before the page was split into three screens |
| `demo/hisabsetu-demo-voice.mp4` | 69.2 s | Hindi | the original full cut, including the transcript-correction beat |

1920×1080, 30 fps, H.264 + AAC, burned-in captions.

Both 60-second cuts use **Gnani Timbre v2.5 · Deepak** (male, speed 1.0). The
Hindi narration opens presenter-style — *"Jai Hind doston! Pichhle kuch hafton se
main is par kaam kar raha hoon…"* — and the English one mirrors it word for word
(*"Jai Hind! For the last few weeks I've been working on one thing…"*). The
voice-over is synthesized by the same engine the app answers with, so the demo
is self-hosted all the way down. English is rendered with `TTS_LANG=en-IN` on the
same model and voice. Voice samples for other Timbre voices live in
`demo/audio/samples/`; regenerate the narration with any of them using the env
vars below.

## Beat list (matches [demo-script.md](demo-script.md))

| Time | On screen | Beat |
|---|---|---|
| 0:00 | Hisaab screen, ₹4,600 outstanding, 13 entries | "Jai Hind doston! … ek khata, jo sirf bolne se chalta hai" |
| 0:03 | Bolo screen, mic card | the mic is tapped, the command is spoken |
| 0:08 | transcript + preview | ₹150 credit for Ramesh, ₹450 → ₹600, "Ledger abhi nahi badla hai" |
| 0:17 | success card, hisaab ₹4,750 | Confirm is pressed — now it saves |
| 0:29 | balance card | "Ramesh ji ka ₹600 baaki hai", spoken by Timbre |
| 0:41 | "2 kaam ek saath" card | a two-instruction sentence is refused, both clauses listed |
| 0:57 | hisaab, history 14 entries | nothing moves without Confirm |

(The 60-second cuts drop the correction beat, so the close lands at ~1:00.)

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

### English cut

The picture is re-recorded (captions are burned in), but the spoken commands stay
Hindi — that is what the parser and a real shopkeeper speak:

```powershell
# 1. English voice-over: same Timbre model and voice, English language code
SCRIPT=en TTS_LANG=en-IN TTS_MODEL=timbre-v2.5 TTS_VOICE=Deepak TTS_SPEED=1.0 `
  VOICE_DIR_NAME=voice-en python demo/tts_assets.py

# 2. reset the ledger, then record English captions (~2 min, 4 real STT calls)
RAW_DIR=demo/raw-en DEMO_LANG=en AUDIO_DIR=demo/audio/voice node demo/capture.mjs

# 3. mix: English narration + the Hindi command WAVs
RAW_DIR=demo/raw-en VOICE_DIR=demo/audio/voice-en CMD_VOICE_DIR=demo/audio/voice `
  OUT_SUFFIX=-en CUT=60 python demo/assemble.py
```

`assemble.py` now fits every voice-over line to the gap before the next one, so a
longer English sentence is sped up just enough instead of talking over the next
beat. To refresh the Hindi cut on the current UI, run the same three steps with
`RAW_DIR=demo/raw-hi OUT_SUFFIX=-hi` and no `DEMO_LANG`.

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
