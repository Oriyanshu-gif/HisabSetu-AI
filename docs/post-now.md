# Post it now — LinkedIn + X, step by step

Video to upload: **`demo/hisabsetu-demo-60s.mp4`** — 62.4 s, 7.3 MB, 1920×1080,
30 fps, H.264/AAC, Hindi voice-over + burned-in Hinglish captions.

English version, same picture and beats: **`demo/hisabsetu-demo-60s-en.mp4`** —
60.1 s, 7.1 MB, English voice-over + English captions. Use it for an
English-speaking audience (or as the second post / comment video); everything else
in this file stays the same.

Platform limits (checked Nov 2026): LinkedIn native video allows 3 s – 10 min and
up to 5 GB (1080p is the recommended size); X allows 140 s and 512 MB on a free
account. This file fits both with room to spare.

---

## LinkedIn — the post text (copy all of it)

Most kirana shops already keep a perfect ledger — in their head, in Hindi, out loud.

The problem was never the shopkeeper. It was the software: keyboards, English menus, tiny forms.

So I built **HisabSetu AI** — a voice-first khata. Jai Hind 🙏

You speak a command → it shows a confirmation card → you tap Confirm → only then does the ledger change.

🎙️ “Ramesh ko dedh sau rupaye ka udhaar likh do.”
→ Preview: Ramesh · Udhaar · ₹150 · ₹450 → ₹600
→ Confirm → saved, and the reply is spoken back in Hindi
→ “Ramesh ka kitna udhaar baaki hai?” → ₹600, spoken and written

Built on Gnani’s voice models:
• **Prisma** for speech-to-text, in Hindi and code-mixed Hinglish
• **Timbre** for the spoken replies (Deepak voice in the demo)

What I deliberately did *not* build: a chatbot that guesses money.
The parser is deterministic, so `sawa do sau` is ₹225 and not ₹200. Two
instructions in one breath are refused and split instead of being half-executed.
If a word is misheard, you fix the transcript or the amount before confirming —
nothing is saved until Confirm, and a superseded preview can never be saved later.

Rule-based on purpose: financial accuracy over flash.

341 automated tests, a 21-utterance Hindi/Hinglish evaluation suite, and a live
Prisma → Timbre round trip.

One honest note: the voice in the demo is Gnani Timbre (synthetic), fed in through
the real microphone → STT → parser → Confirm path — the same pipeline a
shopkeeper’s own voice goes through.

60-second demo below 👇

@GnaniAI

#GnaniAI #GreatIndianAIInternshipChallenge #VoiceAI #Hinglish #BuildInPublic

---

## LinkedIn — steps

1. Open LinkedIn on desktop, click **Start a post**.
2. Click the **Video** icon (not “Add a document”) and upload
   `C:\...\demo\hisabsetu-demo-60s.mp4`. Wait until processing reaches 100 %
   and the thumbnail appears.
3. Paste the text above into the post box (video and text go in the **same**
   post — do not put the video in a comment).
4. In the text, delete `@GnaniAI` and retype `@Gnani` — pick the **company page**
   from the dropdown so it becomes a real mention (plain text does not notify them).
5. Confirm both hashtags are spelled exactly:
   `#GnaniAI` and `#GreatIndianAIInternshipChallenge`.
6. Set visibility to **Anyone** (public). A connections-only post does not count.
7. Click **Post**.
8. Immediately add a **first comment** with the technical details (below) and your
   repo link. Links in the body reduce reach; links in the comment do not.
9. Copy the post URL from the “…” menu → **Copy link to post**. You will paste it
   into the submission form when it opens.
10. Keep the post public until shortlisting is done. Reply to comments in the
    first hour — engagement is the selection signal.

### First comment (paste after publishing)

Stack: FastAPI + SQLite, no build step, no LLM in the money path. Amounts are
integer paise; the parser handles Hinglish/Devanagari numerals (`dedh sau` = ₹150,
`sawa do sau` = ₹225).

Gnani integration: Prisma STT (`/stt/v3`, multipart) and Timbre TTS
(`/api/v1/tts/inference`, WAV). Browser recordings (WebM/MP4) are converted to
16 kHz mono WAV with ffmpeg before transcription.

Honest evaluation: 21 supplied quiet/noisy transcripts → all parse to a command,
19 reproduce the intended action exactly, the other 2 are transcription losses in
the supplied audio (₹125 vs ₹225, and a two-amount sentence the app refuses to
guess at). Zero parser failures. Real noisy-shop accuracy is **not** claimed.

Every financial action needs its own preview and its own Confirm — there is no
auto-post path to the ledger.

Code: <your repo link> · Demo video: this post · Fictional sample data only.

---

## X (Twitter) — single post

X counts 280 characters. This is ~235:

```
Kirana ledgers live in the shopkeeper's head — in Hindi, out loud.

HisabSetu AI: speak → preview → Confirm → ledger changes.
Prisma STT + Timbre TTS, deterministic parser, 341 tests.

60s demo ⬇️ @GnaniAI
#GnaniAI #GreatIndianAIInternshipChallenge
```

### X — optional reply in the same thread

```
Under the hood: FastAPI + SQLite, integer paise, no LLM in the money path.
Gnani Prisma for STT, Timbre for the spoken replies.
21-utterance Hinglish eval: 19/21 exact, 0 parser failures. No noisy-shop
accuracy claimed.
```

### X — steps

1. Open `x.com/compose/post`.
2. Click the media icon → **Upload** → choose `demo/hisabsetu-demo-60s.mp4`
   (61 s and 8.8 MB are well inside the 140 s / 512 MB free-account limit).
3. Paste the single-post text above.
4. Type `@Gnani` and select the real account from the dropdown.
5. Post, then reply to your own post with the thread text above.
6. Copy the post URL too, in case the form accepts X links.

---

## Before you press Post — checklist

- [ ] Video uploaded **natively** to LinkedIn and to X (no YouTube/Drive links).
- [ ] `@Gnani` picked from the dropdown, not typed as plain text.
- [ ] `#GnaniAI` and `#GreatIndianAIInternshipChallenge` present, spelled exactly.
- [ ] Post visibility **public**.
- [ ] Numbers match the repo: **341 tests**, 21-case suite, 19/21 exact, 0 parser
      failures. No award, benchmark, user count or real-world accuracy claimed.
- [ ] No API key, `.env`, terminal with secrets, or real customer name on screen —
      every seeded name is fictional.
- [ ] Reply to comments for the first hour.
- [ ] Save both post URLs and fill the **submission form** when it opens
      (deadline noted in the challenge email: **10 Nov, 11:59 PM IST**).
