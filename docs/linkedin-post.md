# LinkedIn post for the Gnani AI internship challenge

Requirements from the challenge email, all covered below: post a **video** of the
build on **LinkedIn or X** (public), **tag Gnani**, and include
**#GnaniAI** and **#GreatIndianAIInternshipChallenge**. Selection is based on
public engagement, and there is a “best 60-second demo” category.

Nothing here is auto-posted. Read it, change the links, post it yourself.

**Submitting:** the email says the submission form opens closer to the deadline;
the post only makes you eligible. Post → keep the link → fill the form when it
opens, and keep the post public until shortlisting is done (engagement is the
selection signal, and the form asks for the post URL).

---

## The post (copy from here)

Most kirana shops already keep a perfect ledger — in their head, in Hindi, out loud.

The problem was never the shopkeeper. It was the software: keyboards, English
menus, tiny forms.

So I built **HisabSetu AI** — a voice-first khata. You speak, it shows a
confirmation card, you tap Confirm, and only then does the ledger change.

🎙️ “Ramesh ko dedh sau rupaye ka udhaar likh do.”
→ Preview: Ramesh · Udhaar · ₹150 · ₹450 → ₹600
→ Confirm → saved, balance updated, reply spoken back in Hindi
→ “Ramesh ji ka kitna udhaar baaki hai?” → answer, spoken and written

Built on Gnani’s voice models:
• **Prisma** for speech-to-text, in Hindi and code-mixed Hinglish
• **Timbre** for the spoken confirmations

What I deliberately did *not* build: a chatbot that guesses money.
The parser is deterministic, so `sawa do sau` is ₹225 and not ₹200. Two
instructions in one breath are refused and split instead of being half-executed.
If the transcript is misheard, you can fix the words or the amount before
confirming — nothing is saved until you press Confirm, and a superseded preview
can never be saved later.

Rule-based on purpose: financial accuracy over flash.

338 automated tests, a 21-utterance Hindi/Hinglish evaluation suite, and a live
Prisma → Timbre round trip verified today.

60-second demo below 👇

@GnaniAI

#GnaniAI #GreatIndianAIInternshipChallenge #VoiceAI #Hinglish #BuildInPublic

---

## 60-second video shot list

Record at 1280×720 or larger, browser zoom ~110 %, no Devanagari clipping.

| Time | On screen | Say / do |
|---|---|---|
| 0:00–0:05 | Dashboard, ₹4,600 outstanding | “Kirana shops already keep this ledger — in their head.” |
| 0:05–0:15 | Mic card | Tap the mic and say **“Ramesh ko dedh sau rupaye ka udhaar likh do.”** |
| 0:15–0:25 | Transcript + preview card | Point at the parsed ₹150 and the ₹450 → ₹600 line; note “Ledger abhi nahi badla hai.” |
| 0:25–0:32 | Confirm | Press **Confirm transaction**, show the success card and the new total. |
| 0:32–0:40 | Balance question | Type or say **“Ramesh ka kitna udhaar baaki hai?”**, then press **Sunao** so the Hindi voice plays. |
| 0:40–0:48 | Compound refusal | Send “Ramesh ko 200 udhaar **aur** Sunita ne 200 jama kiye”, show the two-clause card asking to split. |
| 0:48–0:56 | Correction | On a fresh preview, press **Transcript sudharein**, fix the amount, show the rebuilt preview. |
| 0:56–1:00 | Close | “Nothing is saved without Confirm. That was the whole point.” |

### Award categories this demo honestly fits

Picking two and saying so in the post helps a judge map it to a prize without
you having to overclaim:

| Category | Evidence in this build |
|---|---|
| **Hinglish / code-mixed** | the parser targets spoken Hinglish (`Ramesh ko dedh sau rupaye ka udhaar likh do`), not clean Hindi |
| **Real-world impact** | a working ledger for shops that already do this verbally; money changes only after Confirm |
| **Best 60-second demo** | the shot list above is exactly 60 s |
| **Tier 2 / Tier 3 towns** | the kirana framing and Hindi-first UI are aimed at exactly that user |

Do **not** claim noisy-audio robustness as a result: the noisy tier is documented
in [noisy-audio-eval.md](noisy-audio-eval.md) but real recordings were not run.

If you have 30 extra seconds (for a longer cut): overpayment guard — Sunita’s
balance is ₹150, say “Sunita ne ek hazaar rupaye wapas kar diye”, show the
advance warning and cancel it, proving the ledger is untouched.

**Alt text for the video:** “Screen recording of HisabSetu AI: a Hindi voice
command is transcribed, shown as a ₹150 credit preview for Ramesh with the new
balance, confirmed, and spoken back in Hindi; a two-instruction sentence is
refused with both clauses listed.”

---

## First comment (post it yourself, right after publishing)

Technical detail for anyone who wants it:

- Stack: FastAPI + SQLite, no build step, no LLM in the money path. Amounts are
  integer paise; the parser handles Devanagari/Hinglish numerals (`dedh sau` =
  ₹150, `sawa do sau` = ₹225, `pandreh sau` = ₹1500).
- Gnani integration: Prisma STT (`/stt/v3`, multipart) and Timbre TTS
  (`/api/v1/tts/inference`, WAV). WebM/MP4 browser recordings are converted to
  16 kHz mono WAV with ffmpeg before transcription.
- Honest evaluation: 21 supplied quiet/noisy transcripts → all parse to a command,
  19 reproduce the intended action exactly, the other 2 are transcription losses
  in the supplied audio data (₹125 vs ₹225, and a ledger-style sentence with two
  amounts that the app refuses to guess at). Zero parser failures.
- Every financial action needs its own preview and its own Confirm; there is no
  auto-post path to the ledger.
- Code: <your repo link> · Demo video: this post · Not a commercial product, no
  real customer data anywhere — the ledger is seeded with fictional names.

---

## Short version for X (if you post there too)

Most kirana ledgers live in the shopkeeper’s head, in Hindi, out loud.

I built **HisabSetu AI**: speak a command → see a ₹-exact preview → Confirm →
the ledger changes (and the reply talks back in Hindi).

Prisma STT + Timbre TTS, deterministic parser, 338 tests. 60s ⬇️

@GnaniAI #GnaniAI #GreatIndianAIInternshipChallenge

---

## Before you press Post — checklist

- [ ] Video is uploaded **natively** to LinkedIn (not a YouTube link) and set to
      **Public**.
- [ ] `@GnaniAI` is a real mention — pick the company page from the dropdown so
      it renders as a link, not plain text.
- [ ] Both hashtags present and spelled exactly: `#GnaniAI`,
      `#GreatIndianAIInternshipChallenge`.
- [ ] Links in the first comment, not in the post body (reach).
- [ ] No API key, `.env`, terminal with secrets, or real customer name anywhere
      on screen.
- [ ] Numbers you quote match the repo: **338 tests**, 21-case suite,
      19/21 exact with 0 parser failures — do not inflate them or claim
      real-world accuracy that was not measured.
- [ ] No claim of an award, offer, benchmark or user count.
- [ ] If you also host a public demo, open the URL once *before* posting (free
      tiers sleep) and remember it is unauthenticated — see
      [deploy.md](deploy.md#path-b--render-free-public-demo-docker).
- [ ] Reply to comments for the first hour; engagement is the selection signal.
- [ ] Same demo posted to **X** as well if you want the second platform counted
      (short version above) — the email asks for LinkedIn *or* X, so both is a bonus.
- [ ] Remember the **submission form** (opens nearer the deadline): paste the
      post URL there, not just in a comment.
