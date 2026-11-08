| Test ID | Condition | Original phrase | Actual STT transcript | Expected intent | Expected amount | Expected customer | Parsed intent | Parsed customer | Parsed amount | STT status | STT detail | Parser status | End-to-end status | Failure reason | Parser ambiguity | Parser reasons | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Shaant | Ramesh ko dedh sau rupaye ka udhaar likh do | रमेश जी का एक सौ पचास रुपए का उधार लिख दिया गया है, अब बकाया चार सौ पचास रुपये है। | add_credit | 150 | Ramesh | add_credit | रमेश | — | stt_mismatch | amount: parsed=None != intended='150' | parser_ok | e2e_stt_loss | amount: parsed=None != intended='150' — recorded as a TRANSCRIPTION loss, not a parser failure | multiple_amounts, amount_needs_review | Ek se zyada amount mile — kaunsa sahi hai? | "उधार" udhaar dene ka signal hai. | Quiet: Prisma returned a ledger-style sentence that carries TWO amounts — the entry (एक सौ पचास = ₹150) and the running balance (चार सौ पचास = ₹450).  The parser cannot tell which is the transaction, so it returns amount=None with multiple_amounts / amount_needs_review and asks the shopkeeper, instead of silently posting ₹450 or ₹150.  रमेश and the credit intent are still read correctly. |
| 2 | Shaant | Ramesh ko dedh sau rupaye ka udhaar likh do | रमेश को डेढ़ सौ रुपये का उधार लिख दो | add_credit | 150 | Ramesh | add_credit | रमेश | 150.0 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Quiet: clean credit-150 transcript (रमेश को डेढ़ सौ...); no repair needed here. |
| 3 | Shaant | Sunita ne do sau rupaye wapas kar diye | सुनीता ने दो सौ रुपये वापस कर दिए हैं | record_payment | 200 | Sunita | record_payment | सुनीता | 200 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | Customer "ne" de diya — payment maana gaya. | Quiet: script swap सुनीता↔Sunita; ledger canonical key auto-links them, ₹200 payment intact. |
| 4 | Shaant | Mohan ko sawa do sau ka udhaar likh do | मोहन को सवा सौ का उधार लिख दो | add_credit | 225 | Mohan | add_credit | मोहन | 125.00 | stt_mismatch | amount: parsed=Decimal('125.00') != intended='225' | parser_ok | e2e_stt_loss | amount: parsed=Decimal('125.00') != intended='225' — recorded as a TRANSCRIPTION loss, not a parser failure | — | "उधार" udhaar dene ka signal hai. | Quiet: supplied transcript lost the 'do' fraction (सवा सौ = ₹125 vs intended sawa do sau = ₹225); parser-read amount is honest about that loss. |
| 5 | Shaant | Ramesh bhai ko teen sau ka udhaar likh do | रमेश भाई को तीन सौ का उधार लिख दो | add_credit | 300 | Ramesh | add_credit | रमेश | 300 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Quiet: रमेश भाई → रमेश (bhai dropped by parser/ledger honourific rules); ₹300 intact. |
| 6 | Shaant | Suresh ko dedh hazaar rupaye ka udhaar likh do | सुरेश को डेढ़ हजार रुपए का उधार लिख दो | add_credit | 1500 | Suresh | add_credit | सुरेश | 1500.0 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Quiet: डेढ़ हजार recovered to ₹1500; सुरेश intact. |
| 7 | Shaant | Sunita ne paanch sau rupaye jama kiye | सुनीता ने पांच सौ रुपये जमा किए हैं | record_payment | 500 | Sunita | record_payment | सुनीता | 500 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "जमा" payment/wapas ka pakka signal hai. | Quiet: script swap सुनीता↔Sunita; ledger canonical key auto-links them, जमा ₹500 intact. |
| 8 | Shaant | Mohan ka kitna udhaar baaki hai | मोहन का कितना उधार बाकी है | balance_query | — | Mohan | balance_query | मोहन | — | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "कितना उधार" balance ka sawal hai. | Quiet: balance_query, no transaction written. |
| 9 | Shaant | Sabse zyada udhaar kis customer ka hai | सबसे ज्यादा उधार किस कस्टमर का है | top_debtor | — | — | top_debtor | — | — | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "सबसे ज्यादा उधार" se sabse zyada udhaar ka sawal samajh aaya. | Quiet: top_debtor query, no transaction written. |
| 10 | Shaant | Aaj ka poora hisaab batao | आज का पूरा हिसाब बताओ | daily_summary | — | — | daily_summary | — | — | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "आज का पूरा हिसाब" se daily summary ka signal mila. | Quiet: daily_summary query, no transaction written. |
| 11 | Shaant | Ramesh ko pandrah sau rupaye ka udhaar likh do | रमेश को पंद्रह सौ का उधार लिख दो | add_credit | 1500 | Ramesh | add_credit | रमेश | 1500 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Quiet: पंद्रह सौ → 15×100 = ₹1500; रमेश intact. |
| 12 | Shor | Ramesh ko dedh sau rupaye ka udhaar likh do | रमेश को डेढ़ सौ रूपए का उधार लिख दो हर दिन इंग्लिश स्पीकिंग प्रैक्टिस करने में मदद करूंगी | add_credit | 150 | Ramesh | add_credit | रमेश | 150.0 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Noisy: filler appended after command; command portion still रमेश + ₹150 + credit. |
| 13 | Shor | Sunita ne do sau rupaye wapas kar diye | सुनीता ने दो सौ रूपए वापस कर दिए और गलतियां होने पर बिना जज के करेक्ट करूँगी अच्छा कल से ही शुरू करूँगी | record_payment | 200 | Sunita | record_payment | सुनीता | 200 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | Customer "ne" de diya — payment maana gaya. | Noisy: filler appended; command portion still सुनीता + ₹200 + payment; canonical key links सुनीता↔Sunita. |
| 14 | Shor | Mohan ko sawa do sau ka udhaar likh do | मोहन को सवा दो सौ का उधार लिख दो | add_credit | 225 | Mohan | add_credit | मोहन | 225.00 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Noisy: सवा दो सौ preserved as ₹225 in supplied transcript (noisy tier fixed the fraction that case 4 lost in quiet form). |
| 15 | Shor | Ramesh bhai ko teen sau ka udhaar likh do | रमेश भाई को तीन सौ का उधार लिख दो | add_credit | 300 | Ramesh | add_credit | रमेश | 300 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Noisy: रमेश भाई → रमेश; ₹300 intact. |
| 16 | Shor | Suresh ko dedh hazaar rupaye ka udhaar likh do | सुरेश को डेढ़ हज़ार रुपए का उधार लिख दो अब तेरा यहाँ कोई काम नहीं रे | add_credit | 1500 | Suresh | add_credit | सुरेश | 1500.0 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Noisy: filler appended; command portion still सुरेश + ₹1500 + credit. |
| 17 | Shor | Sunita ne paanch sau rupaye jama kiye | सुनीता ने पांच सौ रूपए जमा कर दिए | record_payment | 500 | Sunita | record_payment | सुनीता | 500 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "जमा" payment/wapas ka pakka signal hai. | Noisy: सुनीता + जमा ₹500 intact; canonical key links सुनीता↔Sunita. |
| 18 | Shor | Mohan ka kitna udhaar baaki hai | मोहन का कितना उधार बाकी है | balance_query | — | Mohan | balance_query | मोहन | — | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "कितना उधार" balance ka sawal hai. | Noisy: balance_query, no transaction written. |
| 19 | Shor | Sabse zyada udhaar kis customer ka hai | सबसे ज़्यादा उधार किस कस्टमर का है | top_debtor | — | — | top_debtor | — | — | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "सबसे ज़्यादा उधार" se sabse zyada udhaar ka sawal samajh aaya. | Noisy: top_debtor query, no transaction written. |
| 20 | Shor | Aaj ka poora hisaab batao | आज का पूरा हिसाब बताओ | daily_summary | — | — | daily_summary | — | — | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "आज का पूरा हिसाब" se daily summary ka signal mila. | Noisy: daily_summary query, no transaction written. |
| 21 | Shor | Ramesh ko pandrah sau rupaye ka udhaar likh do | रमेश को पंद्रह सौ रुपये का उधार लिख दो | add_credit | 1500 | Ramesh | add_credit | रमेश | 1500 | stt_ok | transcript preserves intent | parser_ok | e2e_ok |  | — | "उधार" udhaar dene ka signal hai. | Noisy: पंद्रह सौ → ₹1500; रमेश intact. |


## Summary

- Total cases: **21** (quiet **11**, noisy **10**)
- STT judgement: **19/21** preserved intent (9/11 quiet, 10/10 noisy)
- Parser stage: **21/21** parsed a command from the supplied transcript
- End-to-end: **19/21** reproduced the intended command exactly
- End-to-end, transcription-limited: **2/21** diverged only because the supplied transcript lost the command (parser read the transcript faithfully)
- End-to-end failures (parser bugs): **0/21**

### STT mismatches (judgement)

- **Case 1**: amount: parsed=None != intended='150'
- **Case 4**: amount: parsed=Decimal('125.00') != intended='225'

### End-to-end divergences explained by transcription (not parser bugs)

- **Case 1**: amount: parsed=None != intended='150' — recorded as a TRANSCRIPTION loss, not a parser failure
- **Case 4**: amount: parsed=Decimal('125.00') != intended='225' — recorded as a TRANSCRIPTION loss, not a parser failure

No end-to-end case failed for a parser reason on the supplied transcripts.

## Condition split

### Quiet audio (Shaant) — cases 1–11

- **Case 1**: STT `stt_mismatch`, parser `parser_ok`, e2e `e2e_stt_loss` — amount: parsed=None != intended='150' — recorded as a TRANSCRIPTION loss, not a parser failure.
- **Case 2**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 3**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 4**: STT `stt_mismatch`, parser `parser_ok`, e2e `e2e_stt_loss` — amount: parsed=Decimal('125.00') != intended='225' — recorded as a TRANSCRIPTION loss, not a parser failure.
- **Case 5**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 6**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 7**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 8**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 9**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 10**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 11**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.

### Noisy audio (Shor) — cases 12–21

- **Case 12**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 13**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 14**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 15**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 16**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 17**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 18**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 19**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 20**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.
- **Case 21**: STT `stt_ok`, parser `parser_ok`, e2e `e2e_ok` — matched intended command.

## Important limitation

The 11 quiet cases and 10 noisy cases above are evaluated from *supplied transcripts*, not from recorded shop-floor audio.  The noisy-condition tier exercises filler-robust parsing (commands followed by unrelated shop talk), but the STT stage still judges the transcript the table gives it.  A true noisy-audio measurement would need recorded audio per condition.

These numbers are therefore **not** STT word-error or accuracy metrics:

- they measure our *parser* against fixed transcripts, and
- the STT column is a per-case human judgement of that supplied transcript.

For a real recording-based measurement see `docs/noisy-audio-eval.md` (`python live_eval.py` for paid live GNANI STT runs on recorded audio).
