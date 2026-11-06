# 60-second demo — narration script

Recorded against a **fresh demo DB** so the numbers on screen are:

| What | Value |
|---|---|
| Dashboard total | ₹4,600 |
| Ramesh before | ₹450 |
| After +₹150 credit | ₹600 |
| New dashboard total | ₹4,750 |
| Sunita (bonus beat) | ₹150 → ₹1,000 payment triggers the advance warning |

Two ways to use this:

- **Live narration** — speak while you click. Sounds spontaneous, but the app's
  Hindi TTS plays at the same time; keep the speaker volume low.
- **Voice-over later (recommended)** — record the screen silently, then read this
  script over it in Clipchamp. Timing is easy and nothing overlaps.

---

## The script

**[0:00 — dashboard on screen, ₹4,600 outstanding]**

> Kirana shops already keep a perfect ledger — in their head, out loud, in Hindi.
> The problem was never the shopkeeper. It was the software.

**[0:07 — mic card, tap the mic]**

> So I built HisabSetu AI. Watch — I'll just speak.

🎙 **Say into the mic:** "Ramesh ko dedh sau rupaye ka udhaar likh do."

**[0:15 — transcript + preview card]**

> Prisma transcribed that, and the parser turned it into a ₹150 credit for Ramesh —
> ₹450 becomes ₹600. And notice: the ledger is still untouched.

**[0:25 — press Confirm transaction]**

> Confirm — and only now does it save. New total: ₹4,750.

**[0:32 — type the balance question, then press Sunao]**

🎙 **Say or type:** "Ramesh ka kitna udhaar baaki hai?"

> It answers — and speaks the answer back in Hindi through Timbre.

**[0:40 — send the compound sentence]**

🎙 **Say or type:** "Ramesh ko 200 udhaar aur Sunita ne 200 jama kiye."

> Two instructions in one breath? It refuses, lists both, and asks me to split them —
> instead of half-saving something.

**[0:48 — new preview, press Transcript sudharein]**

> And if it mishears me, I fix the transcript — not the database.

**[0:54 — back to the dashboard]**

> No silent writes. Nothing changes without Confirm. That was the whole point.

---

## Hinglish narration (recorded version — Deepak, Timbre v2.5)

The presenter intro is the recorded take: **"Jai Hind doston! Pichhle kuch hafton
se main is par kaam kar raha hoon…"**. Exact beat timings for the finished video
are in [demo-video.md](demo-video.md); the seconds below are the narration slots.

Speak the 🎙 lines **exactly as written** — they were re-verified against the demo
DB on Nov 3: `dedh sau` → ₹150 (₹450 → ₹600), the balance question → "₹450 baaki
hai", `ek hazaar` for Sunita → overpayment warning. Nothing else needs to be exact;
the narration is yours.

**[0:00 — dashboard, ₹4,600 outstanding]**

> Jai Hind doston! Pichhle kuch hafton se main is par kaam kar raha hoon —
> ek khata, jo sirf bolne se chalta hai.

**[0:07 — mic card, tap the mic]**

> Ye hai HisabSetu AI. Main sirf bolunga.

🎙 **"Ramesh ko dedh sau rupaye ka udhaar likh do."**

**[0:15 — transcript + preview card]**

> Prisma ne suna, parser ne ₹150 ka udhaar bana diya — Ramesh ₹450 se ₹600.
> Aur sabse zaroori baat: ledger abhi nahi badla.

**[0:23 — press Confirm transaction]**

> Confirm dabaya — ab save hua. Total ₹4,750.

**[0:31 — balance question]**

🎙 **"Ramesh ka kitna udhaar baaki hai?"**

> Bakaya poocha — jawab aaya, aur Timbre ne use Hindi mein bol kar sunaya.

**[0:38 — compound sentence]**

🎙 **"Ramesh ko 200 udhaar aur Sunita ne 200 jama kiye."**

> Ek saans mein do hukm? Ye mana kar deta hai, dono dikhata hai, alag-alag
> karne ko kehta hai — aadha save karke chup nahi hota.

**[0:47 — new preview, press Transcript sudharein]**

> Galat suna ho, to main transcript sudharta hoon — database nahi.

**[0:53 — back to the dashboard]**

> Bina Confirm kuch nahi badalta. Yahi is app ka poora idea hai.

Word count ≈ 120 → about 50–55 seconds at a natural Hindi pace, which leaves room
for the app's own Hindi speech to be heard.

## Bonus beat (+30 s, if you're not cutting to 60 s)

Before the close, say: *"Sunita ne ek hazaar rupaye wapas kar diye"* — Sunita's
balance is ₹150, so a ₹1,000 payment is refused as an overpayment/advance until
you acknowledge it. Show the warning, press Cancel, then show the balance is
still ₹150. This is the strongest ledger-safety proof in the build.

> That's the whole guard: money can't move past zero without a second decision.

---

## Click path (so you never get lost)

1. Dashboard → tap **mic** (or type in the box, Enter).
2. Preview card → **Confirm transaction**.
3. Success card → **Aur bolein** (back to the input).
4. Balance question → Enter → **Sunao** (Hindi voice plays).
5. Compound sentence → Enter → refusal card (two clauses + "Isko alag chalayein").
6. New preview → **Transcript sudharein** → change the amount → rebuilt preview.
7. **Cancel** / back to dashboard.

## Before you press record

- Mic permission allowed for `127.0.0.1` in Chrome/Edge.
- 1280×720 or larger, browser zoom 110–115 %, bookmarks bar hidden.
- Notifications off (Win + N → Do Not Disturb).
- No `.env`, terminal with the API key, or real customer name on screen — every
  seeded name is fictional.
- Numbers you quote must match what is on screen. Both the local demo instance and
  the Render deploy seed the same data, so ₹4,600 / ₹450 → ₹600 holds for both.
