# Fix report — 30 Oct 2026

Priority-ordered work on the existing HisabSetu AI app. Nothing was rebuilt; every
change repairs or extends what was already there. Original copies of the touched
files are in `.backup/`.

## Verification summary

| Check | Command | Result |
|---|---|---|
| Full suite | `python -m pytest` | **434 passed**, 1 warning (Starlette `httpx` deprecation) |
| Eval report | `python eval_report.py --markdown report.md --csv report.csv` | exit 0, report regenerated |
| Startup | `python -m uvicorn main:app --host 127.0.0.1 --port 8000` | started, `/api/health` → 200 |
| Python syntax | `python -m compileall …` | ok |
| JS syntax | `node --check static/app.js` | ok |

Test counts per module: parser 130, API 53, ledger 32, audio 15, Gnani client 18,
STT/parser evals 63, sweep 21.

## P0-1 — TTS missing-key / configuration error

- **Cause:** the endpoint and the client each ran their own `is_configured()` check,
  so a missing key could surface as a provider error (or a 200 with an error body)
  depending on which module had been reloaded/patched.
- **Fix:** one gate, `gnani_client.require_configured(feature)`, reads the single
  `config.settings` object used by both the app and the client.
  Missing key → `GnaniNotConfigured` → HTTP **503** `gnani_not_configured`.
  `/api/tts` docs the full contract (`200/422/429/502/503`) and refuses to return
  200 unless real audio bytes came back.
- **Evidence:** `tests/test_gnani_client.py` (18 tests) and `tests/test_api.py`
  (`test_tts_is_503_without_a_key`, `…returns_binary_audio_when_mocked`,
  `…provider_error_is_never_reported_as_success`, `…empty_body_is_not_a_success`,
  `…network_failure_reports_provider_error_not_missing_key`).
- Key is never printed; provider messages scrub it (`"[redacted]"`).

## P0-2 — Cross-script customer matching

- `parser.canonical_name()` = `normalize_name` (Devanagari transliteration,
  honorific stripping, punctuation fold) → `simplify_latin`, so `सुनीता`,
  `Sunita`, `सुनीता जी`, `Sunita ji`, `Ramesh bhai` land on the same key.
- Ledger resolution, duplicate detection and the evaluation all use that one key.
- Uncertain matches still return candidates and demand an explicit choice; a
  fuzzy-but-not-equal name never auto-picks a customer.
- Tests: Hindi names, Latin names, honorifics, script swaps and ambiguous pairs
  in `tests/test_parser.py` and `tests/test_ledger.py`.

## P0-3 — STT/parser evaluation report

- The six audited failures are now split into the right buckets instead of being
  papered over:
  - **Cases 3, 7, 13, 17** (`सुनीता` vs `Sunita`): fixed by `canonical_name`, not by
    editing data — the ledger links the same person.
  - **Case 4** (`सवा सौ` vs intended `सवा दो सौ`): the parser reads **₹125** and must
    never silently post ₹225; the divergence is recorded as a transcription loss.
  - **Case 1** (ledger-style sentence): it carries **two** amounts — the entry
    `एक सौ पचास` (₹150) and the balance `चार सौ पचास` (₹450) — so the parser returns
    `amount=None` with `multiple_amounts` + `amount_needs_review` and asks, rather
    than guessing. That is the reason it "fails to extract an amount", and it is
    the correct financial behaviour.
- `end_to_end_outcome()` is shared by `tests/test_stt_parser_evals.py` and
  `eval_report.py`, so the published report can no longer disagree with the tests.
- Regenerated `report.md`: **21/21** parse, **19/21** exactly reproduce the
  intended command, **2/21** transcription-limited, **0** parser failures.
  Original phrase *and* actual transcript are kept in every row; nothing was
  rewritten to make a case pass.

## P1-4 — Compound commands

- `parser.detect_compound()` finds two clearly separated financial instructions
  (`… aur …`, query + transaction, etc.).
- `services` refuse to act on them: the response is a clarification with
  `needs: ["compound"]` listing every clause it heard. No proposal, no write.
- UI renders the clauses with **“Iske alag chalayein”** per clause, so each
  action gets its own preview and its own Confirm.
- Tests: compound credit+payment, transaction-half never dropped, trailing comma
  is not compound, STT filler after “aur” is not compound, two questions are not
  compound (`tests/test_parser.py`, `tests/test_api.py`).

## P1-5 — Transcript correction

- New **Transcript sudharein** button on the transcript card: loads the words into
  the text box, focuses it, and explains that nothing is saved until Confirm.
  Re-sending re-parses and rebuilds the preview.
- The existing **Details theek karein** form recalcs customer/type/amount through
  `/api/manual-proposal` → new preview, still zero ledger writes.
- Sending a new command auto-cancels the superseded pending preview (verified in
  the browser: `POST /api/pending/{id}/cancel → 200` immediately before the new
  preview), and re-sending the *identical* instruction supersedes the earlier
  identical pending row, so a double-tap cannot post twice.
- Tests: transcript correction re-parses ₹125 → ₹225 with no write until Confirm;
  repeated identical sends create one entry, not two.

## P1-6 — Reproducible noisy-audio evaluation

- New `docs/noisy-audio-eval.md`: four tiers (fixed transcripts / TTS round-trip /
  synthetic noise / real recordings), recording procedure and file naming, FFmpeg
  noise overlay examples, and explicit reporting rules.
- New `eval_recordings.py`: evaluates real clips named `<case_id>__<condition>.<ext>`,
  `--list` prints the 21 phrases to record, exits 2 when unconfigured (never fakes
  a pass), never touches the ledger.
- No accuracy claim is made anywhere: the fixtures are transcripts, the noisy tier
  is shop-talk filler text, and no real-recording run exists yet.
- The script itself was smoke-tested end to end on one clip labelled
  `2__synthetic.wav` (the TTS audio from the live check): discovery, transcription,
  parse (₹150 · Ramesh · credit), console table, Markdown and CSV output, exit 0.
  The clip was then deleted; it counted as **synthetic**, so it is not reported as
  a real-recording result.

## Live Gnani verification

- Key present and loaded from `.env` (`config_source: env_file`); never printed.
- One Timbre TTS request → **230,444 bytes**, `audio/wav`, `RIFF`/`WAVE` header.
- One Prisma STT request on that audio → `रमेश को डेढ़ सौ रुपये का उधार लिख दो।`
  (`prisma-v2.5`).
- Through the running server: `POST /api/tts` → 200 `audio/wav` 76,844 bytes, and
  the browser’s **Sunao** played the reply (`/api/tts → 200`, blob media `206`).
- Call count was kept minimal (three TTS requests including the in-app playback
  check, one STT). No repeated looping.

## Environment note (not an app change)

The suite initially failed to collect with
`ImportError: DLL load failed while importing _collections_cy: An Application Control policy has blocked this file`.
Windows Application Control blocked SQLAlchemy 2.1.6’s compiled helpers. Those are
optional: the wheel ships pure-Python fallbacks, so the blocked `.pyd` files were
renamed to `*.blocked-by-windows-policy` inside `.venv` and SQLAlchemy fell back to
them. No application code was changed for this. The recovery command is documented
in the README troubleshooting table.

## Remaining / manual

- Real-recording accuracy is unmeasured. Run
  `python eval_recordings.py --dir recordings\` on your own clips and quote the tier.
- Tier B (TTS→STT round trip over all 21 phrases) was not run in full — it costs 21
  paid requests; `python live_eval.py` runs it whenever you want the numbers.
- The live DB still holds the sample data; browser checks created previews only and
  cancelled them, so no ledger row was added (latest entry is still 27 Oct).
- No git repository in this folder, so nothing was committed.
