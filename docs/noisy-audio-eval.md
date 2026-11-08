# Noisy-audio evaluation

This document is the procedure for measuring HisabSetu AI on **real speech** and
for stress-testing it with **synthetic** audio. It exists because the numbers in
[report.md](../report.md) are easy to misread: that report scores the *parser*
against fixed transcripts, not the microphone on a shop floor.

Nothing here needs code changes. Everything runs offline except the two live
tiers, which call Gnani and cost one request per clip.

---

## 1. The four evaluation tiers (never mix them in a claim)

| Tier | What it measures | Cost | Script | What you may say about it |
|---|---|---|---|---|
| **A. Fixture transcripts** | parser only, on 21 supplied transcripts | free, offline | `pytest tests/test_stt_parser_evals.py`, `python eval_report.py --markdown report.md` | "parser reproduces X of 21 supplied commands" |
| **B. TTS → STT round trip** | the whole chain, but on *synthetic* speech | Gnani call per case | `python live_eval.py` | "round-trip on TTS speech: X/21" — **not** real-world accuracy |
| **C. Synthetic noise overlay** | robustness of the chain against added noise / low level | Gnani call per clip | `python eval_recordings.py --dir recordings/` | "synthetic-noise stress test: X/N" — the label *synthetic* must appear in any sentence quoting it |
| **D. Real recordings** | genuine shop-floor speech | Gnani call per clip | `python eval_recordings.py --dir recordings/` | "real recordings: X/N", with the condition, device and clip count stated |

A claim may only quote numbers from a tier that was actually run, and must name
the tier. Tier A numbers are parser numbers. Tier B is synthetic speech. Only
tier D can be described as real-world accuracy, and even then only for the clips
and conditions that were recorded.

No word-error-rate is computed anywhere on purpose: we do not have a labelled
transcript corpus, and inventing a WER would be fiction.

---

## 2. Recording real audio (tier D)

1. Print the phrase list:

   ```bash
   ./.venv/Scripts/python.exe eval_recordings.py --list
   ```

   Each line is `id  [condition]  phrase` — read the *phrase* exactly.

2. Record each phrase **once per condition** you care about:

   - `quiet` — empty room, phone held ~20 cm from the mouth.
   - `noisy` — the real intended setting: fan on, another person talking, TV or
     traffic in the background, phone on the counter rather than in the hand.
   - any other label you like (`shop`, `rush`, `fan-high`); it is used for
     grouping in the summary only.

3. Save with the required name — `<case_id>__<condition>.<ext>`, for example:

   ```
   recordings/3__quiet.wav
   recordings/13__noisy.m4a
   recordings/13__shop.m4a
   ```

   WAV, MP3, OGG, FLAC, AAC, M4A, WebM and MP4 are accepted (WebM/MP4 need
   FFmpeg installed — see the README's FFmpeg note).

4. Run it:

   ```bash
   ./.venv/Scripts/python.exe eval_recordings.py --dir recordings/ \
       --markdown recordings_report.md --csv recordings_report.csv
   ```

5. Report exactly what came back: clip count, conditions, the per-clip table and
   the mismatches. If a phrase was misread, keep its transcript in the report —
   do not re-record until it "passes" and then quote the retry only.

Each clip is one paid STT request. A full 21-phrase pass in two conditions is
42 requests; use `--only 3,7,13,17` to spend fewer.

---

## 3. Synthetic noise (tier C) — always labelled synthetic

Take a clean clip of the phrase and overlay noise with FFmpeg. Two examples:

```bash
# Add babble/traffic noise at ~5 dB SNR (mix, do not replace the speech).
ffmpeg -i clean.wav -i shop_noise.wav \
  -filter_complex "[0:a]volume=1.0[s];[1:a]volume=0.35[n];[s][n]amix=inputs=2:duration=first" \
  noisy.wav

# Simulate a quiet/distant recording: -18 dB and a little room tone.
ffmpeg -i clean.wav -af "volume=0.125,highpass=f=120" quiet.wav
```

Name synthetic results `13__synthetic-noise.wav` so the condition column itself
says what the audio is. Any sentence quoting tier C numbers must contain the
word *synthetic*.

Synthetic noise is a stress test of the pipeline — it is **not** evidence about
a real shop. Do not present it as robustness to real-world noise.

---

## 4. Tier A and B, for reference

```bash
# Tier A — parser against the 21 supplied transcripts (free, deterministic).
./.venv/Scripts/python.exe eval_report.py --markdown report.md --csv report.csv
./.venv/Scripts/python.exe -m pytest tests/test_stt_parser_evals.py -q

# Tier B — TTS -> Gnani STT -> parser on all 21 phrases (paid, synthetic speech).
./.venv/Scripts/python.exe live_eval.py --markdown live_report.md
```

`live_eval.py` and `eval_recordings.py` exit `2` when `GNANI_API_KEY` is missing
so a skip is never confused with a pass, and `1` when a case mismatched.

---

## 5. What has actually been measured so far

Stated precisely, so nothing here can be mistaken for a bigger claim:

- **Tier A (fixtures, offline):** all 21 supplied transcripts parse to a command;
  19 of 21 reproduce the intended command exactly. The two remaining cases
  (case 1 and case 4) are *transcription* losses in the supplied data — case 1's
  ledger-style sentence carries two amounts so the parser returns `amount=None`
  with `multiple_amounts`/`amount_needs_review` instead of guessing, and case 4's
  transcript contains `सवा सौ` (₹125) where the speaker said `सवा दो सौ` (₹225).
  There are **0** end-to-end failures attributable to the parser.
- **Live API reachability:** one real Gnani TTS request returned a 230,444-byte
  RIFF/WAVE file (`audio/wav`), and one real Prisma STT request on that same
  audio returned `रमेश को डेढ़ सौ रुपये का उधार लिख दो।` (model `prisma-v2.5`).
  One clip is a smoke test, not an accuracy measurement.
- **Tier B / C / D:** not run. No real-recordings numbers exist yet, so none are
  quoted anywhere in this repository. Run the commands above in your own
  environment to produce them.
