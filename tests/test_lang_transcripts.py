"""Parser tests built from REAL Prisma transcripts.

Every string below was produced end to end by `eval_langs.py`: Timbre spoke the
sentence in that language, Prisma transcribed it, and the transcript was saved
in `docs/lang-eval.json`. Nothing here is hand-written test data, so a provider
change that breaks the parser shows up as a failing test with the real
transcript in the message.

Regenerate with: `python tools/gen_lang_transcript_tests.py`
"""

from __future__ import annotations

import collections

import pytest

from parser import INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT, parse_command

INTENTS = {INTENT_ADD_CREDIT: "add_credit", INTENT_RECORD_PAYMENT: "record_payment"}

# (language, real transcript, expected amount, expected intent, what was said)
CASES = [
    ('hi-IN', 'रमेश को पचास रुपये का उधार लिख दो।', 50, INTENTS['add_credit'], 'रमेश को पचास रुपये का उधार लिख दो'),
    ('hi-IN', 'सुनीता ने पचास रुपए जमा किए', 50, INTENTS['record_payment'], 'सुनीता ने पचास रुपये जमा किए'),
    ('hi-IN', 'रमेश को एक लाख रुपये का उधार लिख दो।', 100000, INTENTS['add_credit'], 'रमेश को एक लाख रुपये का उधार लिख दो'),
    ('en-IN', 'ramesh ko fifty rupees credit likh do', 50, INTENTS['add_credit'], 'Ramesh ko fifty rupees credit likh do'),
    ('en-IN', 'sunita ne fifty rupees payment diya', 50, INTENTS['record_payment'], 'Sunita ne fifty rupees payment diya'),
    ('en-IN', 'ramesh ko one lakh rupees credit likh do', 100000, INTENTS['add_credit'], 'Ramesh ko one lakh rupees credit likh do'),
    ('bn-IN', 'রমেশকে ₹50 ধার লেখো', 50, INTENTS['add_credit'], 'রমেশকে পঞ্চাশ টাকা ধার লেখো'),
    ('bn-IN', 'সুনীতা ₹50 জমা দিয়েছে', 50, INTENTS['record_payment'], 'সুনীতা পঞ্চাশ টাকা জমা দিয়েছে'),
    ('bn-IN', 'রমেশকে ₹1,00,000 ধার লেখো', 100000, INTENTS['add_credit'], 'রমেশকে এক লাখ টাকা ধার লেখো'),
    ('gu-IN', 'રમેશને પચાસ રૂપિયા ઉધાર લખો', 50, INTENTS['add_credit'], 'રમેશને પચાસ રૂપિયા ઉધાર લખો'),
    ('gu-IN', 'સુનીતાએ પચાસ રૂપિયા જમા કર્યા', 50, INTENTS['record_payment'], 'સુનીતાએ પચાસ રૂપિયા જમા કર્યા'),
    ('gu-IN', 'રમેશને એક લાખ રૂપિયા ઉધાર લખો', 100000, INTENTS['add_credit'], 'રમેશને એક લાખ રૂપિયા ઉધાર લખો'),
    ('kn-IN', 'ರಮೇಶಗೆ ಐವತ್ತು ರೂಪಾಯಿ ಸಾಲ ಬರೀರಿ', 50, INTENTS['add_credit'], 'ರಮೇಶಗೆ ಐವತ್ತು ರೂಪಾಯಿ ಸಾಲ ಬರೆಯಿರಿ'),
    ('kn-IN', 'ಸುನೀತಾ ಐವತ್ತು ರೂಪಾಯಿ ಜಮಾ ಮಾಡಿದ್ದಾರೆ', 50, INTENTS['record_payment'], 'ಸುನೀತಾ ಐವತ್ತು ರೂಪಾಯಿ ಜಮಾ ಮಾಡಿದ್ದಾರೆ'),
    ('kn-IN', 'ರಮೇಶಗೆ ಒಂದು ಲಕ್ಷ ರೂಪಾಯಿ ಸಾಲ ಬರೀರಿ', 100000, INTENTS['add_credit'], 'ರಮೇಶಗೆ ಒಂದು ಲಕ್ಷ ರೂಪಾಯಿ ಸಾಲ ಬರೆಯಿರಿ'),
    ('ml-IN', 'രമേശിന് ₹50 കടമെഴുതൂ', 50, INTENTS['add_credit'], 'രമേശ്ന് അമ്പത് രൂപ കടം എഴുതൂ'),
    ('ml-IN', 'സുനിത ₹50 അടച്ചു', 50, INTENTS['record_payment'], 'സുനിത അമ്പത് രൂപ അടച്ചു'),
    ('ml-IN', 'രമേശിന് ₹1,00,000 കടമെഴുതൂ', 100000, INTENTS['add_credit'], 'രമേശ്ന് ഒരു ലക്ഷം രൂപ കടം എഴുതൂ'),
    ('mr-IN', 'रमेशला पन्नास रुपये उधार लिही', 50, INTENTS['add_credit'], 'रमेशला पन्नास रुपये उधार लिही'),
    ('mr-IN', 'सुनीताने पन्नास रुपये जमा केले', 50, INTENTS['record_payment'], 'सुनीताने पन्नास रुपये जमा केले'),
    ('mr-IN', 'रमेशला एक लाख रुपये उधार लिही', 100000, INTENTS['add_credit'], 'रमेशला एक लाख रुपये उधार लिही'),
    ('pa-IN', 'ਰਮੇਸ਼ ਨੂੰ ਪੰਜਾਹ ਰੁਪਏ ਉਧਾਰ ਲਿਖੋ', 50, INTENTS['add_credit'], 'ਰਮੇਸ਼ ਨੂੰ ਪੰਜਾਹ ਰੁਪਏ ਉਧਾਰ ਲਿਖੋ'),
    ('pa-IN', 'ਸੁਨੀਤਾ ਨੇ ਪੰਜਾਹ ਰੁਪਏ ਜਮਾਂ ਕੀਤੇ', 50, INTENTS['record_payment'], 'ਸੁਨੀਤਾ ਨੇ ਪੰਜਾਹ ਰੁਪਏ ਜਮ੍ਹਾ ਕੀਤੇ'),
    ('pa-IN', 'ਰਮੇਸ਼ ਨੂੰ ਇੱਕ ਲੱਖ ਰੁਪਏ ਉਧਾਰ ਲਿਖੋ', 100000, INTENTS['add_credit'], 'ਰਮੇਸ਼ ਨੂੰ ਇੱਕ ਲੱਖ ਰੁਪਏ ਉਧਾਰ ਲਿਖੋ'),
    ('ta-IN', 'ரமேஷுக்கு ஐம்பது ரூபாய் கடன் எழுது', 50, INTENTS['add_credit'], 'ரமேஷ்க்கு ஐம்பது ரூபாய் கடன் எழுது'),
    ('ta-IN', 'சுனிதா ஐம்பது ரூபாய் செலுத்தினார்', 50, INTENTS['record_payment'], 'சுனிதா ஐம்பது ரூபாய் செலுத்தினார்'),
    ('ta-IN', 'ரமேஷுக்கு ஒரு லட்ச ரூபாய் கடன் எழுது', 100000, INTENTS['add_credit'], 'ரமேஷ்க்கு ஒரு லட்சம் ரூபாய் கடன் எழுது'),
    ('te-IN', 'రమేష్ కి యాభై రూపాయలు అప్పు రాయి', 50, INTENTS['add_credit'], 'రమేష్కి యాభై రూపాయలు అప్పు రాయి'),
    ('te-IN', 'సునీత యాభై రూపాయలు జమ చేశారు', 50, INTENTS['record_payment'], 'సునీత యాభై రూపాయలు జమ చేశారు'),
    ('te-IN', 'రమేష్ కి ఒక లక్ష రూపాయల అప్పు రాయి', 100000, INTENTS['add_credit'], 'రమేష్కి ఒక లక్ష రూపాయలు అప్పు రాయి'),
]


@pytest.mark.parametrize("language, transcript, amount, intent, _said", CASES)
def test_real_transcript_is_understood(language, transcript, amount, intent, _said):
    parsed = parse_command(transcript, language)
    assert parsed.amount_rupees == amount
    assert parsed.intent == intent
    assert parsed.customer_name, f"no customer in {transcript!r}"
    assert parsed.executable is True


def test_every_language_has_real_transcripts():
    counts = collections.Counter(case[0] for case in CASES)
    assert len(counts) == 10
    assert min(counts.values()) >= 2
