# HisabSetu AI: Solution Pitch

**Problem.** Kirana shops still track udhaar (credit) in notebooks. Entries get missed, amounts get written wrong, notebooks get lost, and disputes follow. Payments went digital (UPI, soundboxes); credit bookkeeping did not.

**Solution.** HisabSetu AI is a voice-first udhaar ledger, available today as an app and website (runs in the browser on a phone or computer). The shopkeeper speaks, for example "Ramesh ko dedh sau ka udhaar likh do", and the ledger updates after one confirmation.

**How it works.**
Mic -> Gnani Prisma (speech-to-text) -> Hinglish parser -> Preview -> Confirm -> Ledger (SQLite) -> Gnani Timbre (spoken reply).

**Key features.**
- Hinglish number parser: dedh, dhai, sawa, paune, saade, sau, hazaar, lakh. Ambiguous speech-to-text output is flagged, never guessed.
- Preview-then-Confirm: nothing is saved until the shopkeeper confirms. The transcript can be corrected or cancelled.
- Safety: duplicate-confirm protection (idempotent commit) and an overpayment warning.
- Voice queries: "Ramesh ka kitna baaki?", "Aaj ka poora hisaab", with spoken replies.
- Dashboard: total outstanding, top debtors, history, reminder suggestions (nothing is sent to customers automatically).
- First-run language chooser for both voice and interface: Hindi, English, Bengali, Gujarati, Kannada, Malayalam, Marathi, Punjabi, Tamil, Telugu (plus a Hinglish interface option).
- 434 automated tests. All demo data is synthetic.

**Why Gnani.** Prisma handles Indian-language speech; Timbre gives the shopkeeper a spoken confirmation, which matters at a busy counter where hands and eyes are occupied.

**Evidence and honest limits.**
- Language evaluation (docs/lang-eval.md): 15 sentences per language, Timbre speech -> Prisma -> parser, 150/150 passed in the chosen STT format. This uses clean synthetic speech, not real shopkeepers or noisy shops.
- Real recordings (author's own, small sample): 21 clips, 11 quiet and 10 noisy, one speaker and one device. 19/21 matched the intended command end-to-end; the 2 misses were transcription losses, not parser failures. This is not a general accuracy claim, and wider testing with more speakers and real shops is still to be done.
- Prisma can mishear numbers (for example "sawa do sau" can come back as "sawa sau"), which is why the app always asks for confirmation.
- The demo voice is synthetic (Gnani Timbre).

**Future scope.** Wider real-shop testing with more speakers and devices, automatic UPI payment entry, offline mode, permission-based customer reminders, and, as a future possibility only (not built), a soundbox-style device for the counter.

**Links.** Live: https://hisaabsetu.xyz  |  Code: https://github.com/Oriyanshu-gif/HisabSetu-AI
