"""Deterministic Hindi/Hinglish parser tests (no database, no network)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from parser import (
    INTENT_ADD_CREDIT,
    INTENT_BALANCE_QUERY,
    INTENT_DAILY_SUMMARY,
    INTENT_RECORD_PAYMENT,
    INTENT_TOP_DEBTOR,
    INTENT_UNKNOWN,
    canonical_name,
    detect_compound,
    name_similarity,
    normalize_name,
    normalize_text,
    parse_command,
    transliterate_devanagari,
)


def amount(text: str) -> Decimal | None:
    return parse_command(text).amount_rupees


# ---------------------------------------------------------------------------
# Amount extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ramesh ko dedh sau rupaye ka udhaar likh do", "150"),
        ("Sunita ko dhai sau rupaye udhaar", "250"),
        ("sawa do sau rupaye ka udhaar", "225"),
        ("paanch hazaar udhaar", "5000"),
        ("do hazaar paanch sau ka udhaar", "2500"),
        ("150 rupaye udhaar", "150"),
        ("ढाई सौ रुपये का उधार", "250"),
        ("₹500 udhaar", "500"),
        ("paune do sau ka udhaar", "175"),
        ("saade do sau ka udhaar", "250"),
        ("saade teen sau ka udhaar", "350"),
        ("sawa sau udhaar", "125"),
        ("paune sau udhaar", "75"),
        ("ek lakh udhaar", "100000"),
        ("do lakh pachaas hazaar udhaar", "250000"),
        ("1,500 ka udhaar", "1500"),
        ("dedh hazaar udhaar", "1500"),
        ("1.5 hazaar udhaar", "1500"),
        ("pachaas rupaye udhaar", "50"),
        ("आठ सौ रुपये उधार", "800"),
        ("पांच हज़ार रुपये उधार", "5000"),
        ("bara sau rupaye udhaar", "1200"),
        ("do sau pachaas hazaar udhaar", "250000"),
    ],
)
def test_amount_forms(text, expected):
    assert amount(text) == Decimal(expected)


def test_amount_span_is_recorded():
    parsed = parse_command("Ramesh ko dedh sau rupaye ka udhaar likh do")
    assert parsed.amount_span == "dedh sau"


def test_verb_do_is_not_read_as_two_rupees():
    parsed = parse_command("Ramesh ko udhaar likh do")
    assert parsed.amount_rupees is None
    assert "missing_amount" in parsed.ambiguity
    assert parsed.executable is False


def test_do_sau_is_still_two_hundred():
    parsed = parse_command("Sunita ne do sau rupaye wapas kar diye")
    assert parsed.amount_rupees == Decimal("200")


def test_zero_amount_is_rejected():
    parsed = parse_command("Ramesh ko 0 rupaye udhaar")
    assert parsed.amount_rupees is None
    assert "invalid_amount" in parsed.ambiguity
    assert parsed.executable is False


def test_amount_above_limit_is_rejected():
    parsed = parse_command("Ramesh ko do crore udhaar")
    assert parsed.amount_rupees is None
    assert "invalid_amount" in parsed.ambiguity


def test_multiple_amounts_are_ambiguous():
    parsed = parse_command("Ramesh ko 150 aur Sunita ko 200 udhaar")
    assert "multiple_amounts" in parsed.ambiguity
    assert parsed.amount_rupees is None
    assert parsed.executable is False


# ---------------------------------------------------------------------------
# Intents
# ---------------------------------------------------------------------------


def test_add_credit_intent_and_customer():
    parsed = parse_command("Ramesh ko dedh sau rupaye ka udhaar likh do")
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.customer_name == "Ramesh"
    assert parsed.amount_rupees == Decimal("150")
    assert parsed.executable is True
    assert parsed.ambiguity == []


def test_payment_intent_with_wapas():
    parsed = parse_command("Sunita ne do sau rupaye wapas kar diye")
    assert parsed.intent == INTENT_RECORD_PAYMENT
    assert parsed.customer_name == "Sunita"
    assert parsed.amount_rupees == Decimal("200")
    assert parsed.executable is True


def test_payment_intent_with_jama():
    parsed = parse_command("Mohan ne paanch sau rupaye jama kiye")
    assert parsed.intent == INTENT_RECORD_PAYMENT
    assert parsed.amount_rupees == Decimal("500")


def test_payment_intent_with_ne_and_de_diye():
    parsed = parse_command("Kavita ne paise de diye")
    assert parsed.intent == INTENT_RECORD_PAYMENT
    assert parsed.customer_name == "Kavita"
    assert "missing_amount" in parsed.ambiguity


def test_ko_de_diye_is_credit_not_payment():
    parsed = parse_command("Mohan ko paise de diye")
    assert parsed.intent == INTENT_ADD_CREDIT


def test_balanced_query_is_not_a_transaction():
    parsed = parse_command("Mohan ka kitna udhaar baaki hai?")
    assert parsed.intent == INTENT_BALANCE_QUERY
    assert parsed.customer_name == "Mohan"
    assert parsed.is_query is True
    assert parsed.executable is False


def test_top_debtor_intent():
    parsed = parse_command("Sabse zyada udhaar kis customer ka hai?")
    assert parsed.intent == INTENT_TOP_DEBTOR
    assert parsed.customer_name is None


def test_daily_summary_intent():
    parsed = parse_command("Aaj ka poora hisaab batao.")
    assert parsed.intent == INTENT_DAILY_SUMMARY
    assert parsed.executable is False


def test_devanagari_payment_intent():
    parsed = parse_command("सुनीता ने दो सौ रुपये वापस कर दिए")
    assert parsed.intent == INTENT_RECORD_PAYMENT
    assert parsed.customer_name == "सुनीता"
    assert parsed.amount_rupees == Decimal("200")


def test_devanagari_credit_intent():
    parsed = parse_command("रमेश को डेढ़ सौ रुपये का उधार लिख दो")
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.customer_name == "रमेश"
    assert parsed.amount_rupees == Decimal("150")
    assert parsed.executable is True


def test_unclear_intent_is_not_executable():
    parsed = parse_command("namaste kaise hain aap")
    assert parsed.intent == INTENT_UNKNOWN
    assert parsed.executable is False
    assert "unclear_intent" in parsed.ambiguity


def test_empty_text_is_unknown():
    parsed = parse_command("   ")
    assert parsed.intent == INTENT_UNKNOWN
    assert parsed.executable is False


def test_conflicting_transaction_and_query():
    parsed = parse_command("Ramesh ko 500 udhaar likho aur kitna baaki hai")
    assert "conflicting_intent" in parsed.ambiguity
    assert parsed.executable is False


def test_missing_customer_blocks_execution():
    parsed = parse_command("500 rupaye ka udhaar likh do")
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.customer_name is None
    assert "missing_customer" in parsed.ambiguity
    assert parsed.executable is False


def test_udhaar_wapas_is_payment():
    parsed = parse_command("Ramesh ne udhaar wapas kar diya")
    assert parsed.intent == INTENT_RECORD_PAYMENT


# ---------------------------------------------------------------------------
# Customer names
# ---------------------------------------------------------------------------


def test_customer_via_ke_naam():
    parsed = parse_command("Ramesh ke naam 1500 ka udhaar likh do")
    assert parsed.customer_name == "Ramesh"


def test_customer_after_postposition_variants():
    assert parse_command("Mohan ki udhaar 200 rupaye").customer_name == "Mohan"
    assert parse_command("सीमा को दो सौ उधार").customer_name == "सीमा"


def test_customer_honorific_is_ignored():
    parsed = parse_command("Ramesh ji ne do sau rupaye jama kiye")
    assert parsed.intent == INTENT_RECORD_PAYMENT
    assert parsed.customer_name == "Ramesh"


def test_normalize_name_strips_honorifics_and_case():
    assert normalize_name("  Ramesh   ji ") == "ramesh"
    assert normalize_name("SUNITA") == "sunita"


def test_transliteration_and_fuzzy_matching():
    assert transliterate_devanagari("रमेश") == "ramesh"
    assert normalize_name("रमेश") == "ramesh"
    assert name_similarity("Ramesh", "Ramesh Kumar") >= 0.85
    assert name_similarity("Ramessh", "Ramesh") >= 0.8
    assert name_similarity("Sunita", "Mohan") < 0.4


def test_normalization_keeps_devanagari_matras():
    assert normalize_text("ढाई सौ रुपये") == "ढाई सौ रुपये"
    assert parse_command("ढाई सौ रुपये उधार").amount_rupees == Decimal("250")


def test_glued_digits_and_words_are_split():
    parsed = parse_command("Ramesh ko 150rupaye ka udhaar likh do")
    assert parsed.amount_rupees == Decimal("150")
    assert parsed.customer_name == "Ramesh"


def test_confidence_is_high_only_when_actionable():
    clear = parse_command("Ramesh ko dedh sau udhaar likh do")
    vague = parse_command("Ramesh ko udhaar likh do")
    assert clear.confidence > vague.confidence
    assert clear.confidence >= 0.9


# ---------------------------------------------------------------------------
# Relationship words must not swallow the customer name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_name"),
    [
        ("Ramesh bhai ko teen sau ka udhaar likh dena", "Ramesh"),
        ("Suresh bhaiya ka kitna udhaar baaki hai", "Suresh"),
        ("Mohan bhaiyya ko 200 ka udhaar likh do", "Mohan"),
        ("Kavita didi ne paanch sau rupaye jama kiye", "Kavita"),
        ("Anil chacha ko sau rupaye ka udhaar likh do", "Anil"),
        ("Sunita chachi ka kitna udhaar baaki hai", "Sunita"),
        ("Ramesh mausi ko 150 udhaar likh do", "Ramesh"),
        ("Priya bhabhi ko do sau udhaar likh do", "Priya"),
        ("Mohan uncle ko teen sau ka udhaar likh do", "Mohan"),
        ("Meena aunty ka kitna udhaar baaki hai", "Meena"),
        ("Ramesh sir ko 300 ka udhaar likh do", "Ramesh"),
        ("Kavita madam ne 200 rupaye jama kiye", "Kavita"),
    ],
)
def test_relationship_word_is_skipped_like_honorific(text, expected_name):
    parsed = parse_command(text)
    assert parsed.customer_name == expected_name
    assert "missing_customer" not in parsed.ambiguity


@pytest.mark.parametrize(
    "text",
    [
        "रमेश भाई को तीन सौ का उधार लिख दो",
        "सुरेश भैया का कितना उधार बाकी है",
        "कविता दीदी को दो सौ उधार",
        "अनिल चाचा को सौ रुपये उधार",
        "सीमा चाची ने पांच सौ जमा किए",
        "रमेश मौसी को 150 उधार",
        "प्रिया भाभी को दो सौ उधार",
        "मोहन सर को तीन सौ उधार",
        "सुनीता मैडम ने सौ रुपये जमा किए",
    ],
)
def test_devanagari_relationship_word_is_skipped(text):
    parsed = parse_command(text)
    assert parsed.customer_name is not None
    assert "missing_customer" not in parsed.ambiguity


def test_relationship_word_does_not_change_the_amount():
    parsed = parse_command("Ramesh bhai ko teen sau ka udhaar likh dena")
    assert parsed.customer_name == "Ramesh"
    assert parsed.amount_rupees == Decimal("300")


# ---------------------------------------------------------------------------
# Customer names that are also number words
# ---------------------------------------------------------------------------


def test_number_word_name_does_not_split_the_amount():
    parsed = parse_command("Das ko do sau udhaar")
    assert parsed.customer_name == "Das"
    assert parsed.amount_rupees == Decimal("200")
    assert "multiple_amounts" not in parsed.ambiguity
    assert parsed.executable is True


def test_multi_token_number_word_name_is_kept_whole():
    parsed = parse_command("Sat Pal ko sau rupaye udhaar")
    assert parsed.customer_name == "Sat Pal"
    assert parsed.amount_rupees == Decimal("100")
    assert "multiple_amounts" not in parsed.ambiguity
    assert parsed.executable is True


@pytest.mark.parametrize(
    "text",
    [
        "Ek ko sau rupaye udhaar",
        "Teen ko do sau ka udhaar likh do",
        "Das ji ko paanch sau udhaar",
    ],
)
def test_number_word_name_with_honorific(text):
    parsed = parse_command(text)
    assert parsed.customer_name is not None
    assert "multiple_amounts" not in parsed.ambiguity
    assert parsed.amount_rupees is not None


def test_regular_name_amount_pair_is_unchanged():
    parsed = parse_command("Priya ko paanch sau diye")
    assert parsed.customer_name == "Priya"
    assert parsed.amount_rupees == Decimal("500")
    assert "multiple_amounts" not in parsed.ambiguity


def test_leading_digits_still_win_over_the_name_rule():
    # The rule only fires when the leading span has no digits, so the digits stay
    # in play as amounts and "Ramesh" is still found by the normal path.
    parsed = parse_command("200 Ramesh ko 300 ka udhaar likh do")
    assert parsed.customer_name != "200 Ramesh"
    assert parsed.customer_name == "Ramesh"


def test_scale_word_prefix_is_not_treated_as_a_name():
    # "paanch sau" is an amount, not a customer, so the rule must not fire.
    parsed = parse_command("paanch sau ramesh ko udhaar")
    assert parsed.customer_name != "Paanch"
    assert parsed.amount_rupees == Decimal("500")


# ---------------------------------------------------------------------------
# STT repair: Prisma hears "dedh" as "de do"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("रमेश को दे दो सौ रुपए का उधार लिख दो", "150"),
        ("रमेश को दे दो हज़ार रुपए का उधार लिख दो", "1500"),
        ("Ramesh ko de do sau rupaye ka udhaar likh do", "150"),
    ],
)
def test_de_do_before_scale_word_is_read_as_dedh(text, expected):
    parsed = parse_command(text)
    assert parsed.amount_rupees == Decimal(expected)
    assert "assumed_dedh" in parsed.ambiguity


def test_assumed_dedh_is_reported_as_a_reason():
    parsed = parse_command("रमेश को दे दो सौ रुपए का उधार लिख दो")
    assert any("dedh sau" in reason for reason in parsed.reasons)


def test_real_prisma_transcript_keeps_the_customer():
    # Exact transcript Prisma returned for "dedh sau" in the live run.
    parsed = parse_command("रमेश को दे दो सौ रुपए का उधार लिख दो")
    assert parsed.customer_name == "रमेश"
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.amount_rupees == Decimal("150")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # amount before the verb is a natural imperative: no repair
        ("Ramesh ko sau rupaye de do", "100"),
        # a real "dedh" never needs repair and must not be flagged
        ("Ramesh ko dedh sau rupaye ka udhaar likh do", "150"),
        # "do sau" is the numeral two hundred, not "de do"
        ("Ramesh ko do sau udhaar likh do", "200"),
        ("Ramesh ko paanch sau udhaar de do", "500"),
    ],
)
def test_natural_phrasings_are_not_repaired(text, expected):
    parsed = parse_command(text)
    assert parsed.amount_rupees == Decimal(expected)
    assert "assumed_dedh" not in parsed.ambiguity


def test_repair_does_not_fire_after_a_number():
    # "paanch sau de do sau" is nonsense, but the guard must not rewrite it.
    parsed = parse_command("paanch sau de do sau")
    assert "assumed_dedh" not in parsed.ambiguity


# ---------------------------------------------------------------------------
# STT spelling variants Prisma actually returns for fractions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "word",
    ["डेढ़", "डेढ", "देद", "dedh", "dhedh"],
)
def test_every_dedh_spelling_reads_as_one_point_five(word):
    """Prisma drops the ढ़ and returns "देद"; it must still be ₹150."""
    parsed = parse_command(f"Ramesh ko {word} sau rupaye ka udhaar likh do")
    assert parsed.amount_rupees == Decimal("150")
    assert parsed.customer_name == "Ramesh"


@pytest.mark.parametrize(
    "word",
    ["सवा", "सवाय", "सावा", "सांवा", "साँवा", "सावाँ", "sawa", "sava", "sawaa"],
)
def test_every_sawa_spelling_reads_as_plus_a_quarter(word):
    """Prisma returns long-आ and nasalised forms; two hundred plus a quarter is ₹225."""
    parsed = parse_command(f"Mohan ko {word} do sau ka udhaar likh do")
    assert parsed.amount_rupees == Decimal("225")
    assert parsed.customer_name == "Mohan"


def test_live_nasalised_sawa_transcript_posts_two_hundred_twenty_five():
    """The exact "सांवा" text that still posted ₹200 must now be ₹225."""
    parsed = parse_command("मोहन को सांवा दो सौ का उधार लिख दो।")
    assert parsed.amount_rupees == Decimal("225")
    assert parsed.customer_name == "मोहन"
    assert parsed.executable is True


def test_live_phrase_four_transcript_posts_two_hundred_twenty_five():
    """The exact Prisma text that silently posted ₹200 must now be ₹225."""
    parsed = parse_command("मोहन को सावा दो सौ का उधार लिख दो।")
    assert parsed.amount_rupees == Decimal("225")
    assert parsed.customer_name == "मोहन"
    assert parsed.intent == INTENT_ADD_CREDIT
    assert parsed.executable is True
    assert "multiple_amounts" not in parsed.ambiguity


def test_live_ded_transcript_posts_one_hundred_fifty():
    """The "देद" hearing that silently posted ₹100 must now be ₹150."""
    parsed = parse_command("रमेश को देद सौ रुपए का उधार लिख दो")
    assert parsed.amount_rupees == Decimal("150")
    assert parsed.customer_name == "रमेश"
    assert parsed.executable is True


def test_dedh_hazaar_spelling_still_scales_to_thousands():
    parsed = parse_command("रमेश को देद हज़ार रुपए का उधार लिख दो")
    assert parsed.amount_rupees == Decimal("1500")


def test_sawa_name_position_does_not_silently_post_a_wrong_amount():
    # "सावा" is now a fraction word, so if it opens the sentence it can no longer
    # be confirmed as a customer name; the parser must ask instead of guessing.
    parsed = parse_command("सावा को दो सौ उधार")
    assert parsed.executable is False
    assert parsed.customer_name is None
    assert "missing_customer" in parsed.ambiguity


def test_devanagari_sawa_sau_is_125_and_sawa_do_sau_is_225():
    """Eval case 4 keeps its distinction: सवा सौ = ₹125, सवा दो सौ = ₹225.

    The supplied transcript for that case literally says सवा सौ, so the parser
    must report ₹125 and must never substitute the ₹225 the speaker intended.
    """
    assert amount("मोहन को सवा सौ का उधार लिख दो") == Decimal("125")
    assert amount("मोहन को सवा दो सौ का उधार लिख दो") == Decimal("225")
    assert amount("Mohan ko sawa sau ka udhaar likh do") == Decimal("125")
    assert amount("Mohan ko sawa do sau ka udhaar likh do") == Decimal("225")


def test_two_amounts_are_never_resolved_silently():
    """Eval case 1: a ledger sentence carries entry + running balance.

    Two amounts means the parser asks instead of picking one.
    """
    parsed = parse_command(
        "रमेश जी का एक सौ पचास रुपए का उधार लिख दिया गया है, अब बकाया चार सौ पचास रुपये है।"
    )
    assert parsed.amount_rupees is None
    assert "multiple_amounts" in parsed.ambiguity
    assert "amount_needs_review" in parsed.ambiguity
    assert parsed.intent == INTENT_ADD_CREDIT


# ---------------------------------------------------------------------------
# Cross-script / honorific customer keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("सुनीता", "Sunita"),
        ("रमेश", "Ramesh"),
        ("मोहन", "Mohan"),
        ("सुरेश", "Suresh"),
        ("कविता", "Kavita"),
        ("रमेश भाई", "Ramesh"),
        ("Ramesh bhai", "Ramesh"),
        ("रमेश जी", "Ramesh"),
        ("श्री रमेश", "Ramesh"),
        ("Sunita ji", "सुनीता"),
    ],
)
def test_canonical_name_links_script_and_honorific_variants(left, right):
    """One person, one ledger key — regardless of script or spoken honorific."""
    assert canonical_name(left) == canonical_name(right)
    assert name_similarity(left, right) == 1.0


def test_canonical_name_does_not_merge_different_people():
    """Cross-script folding must not blur distinct customers."""
    assert canonical_name("Ramesh") != canonical_name("Ramesh Kumar")
    assert canonical_name("Mohan") != canonical_name("Mohanlal")
    assert canonical_name("Sunita") != canonical_name("Sunita Devi")
    assert canonical_name("Kavita") != canonical_name("Kavita Sharma")


def test_honorific_only_name_keeps_a_usable_key():
    """A customer actually called 'Bhai' must not normalise to an empty key."""
    assert canonical_name("Bhai") == "bhai"
    assert canonical_name("जी") != ""


# ---------------------------------------------------------------------------
# Compound utterances
# ---------------------------------------------------------------------------


def test_detect_compound_finds_two_separate_commands():
    clauses = detect_compound(
        "Ramesh ko dedh sau rupaye ka udhaar likh do aur Sunita ne do sau wapas kar diye"
    )
    assert len(clauses) == 2
    intents = [parsed.intent for _text, parsed in clauses]
    assert intents == [INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT]
    assert [parsed.amount_rupees for _text, parsed in clauses] == [Decimal("150"), Decimal("200")]


def test_detect_compound_catches_query_plus_transaction():
    """The case that used to silently drop the credit half."""
    clauses = detect_compound("Aaj ka poora hisaab batao aur Ramesh ko 200 ka udhaar likh do")
    assert len(clauses) == 2
    assert any(parsed.intent == INTENT_ADD_CREDIT for _t, parsed in clauses)


def test_detect_compound_ignores_a_single_command():
    assert detect_compound("Ramesh ko dedh sau rupaye ka udhaar likh do") == []
    assert detect_compound("Ramesh ko 150 rupaye ka udhaar likh do, theek hai?") == []


def test_detect_compound_ignores_stt_filler_after_aur():
    """Noisy fixtures append filler after और — that must not read as two commands."""
    clauses = detect_compound(
        "सुनीता ने दो सौ रूपए वापस कर दिए और गलतियां होने पर बिना जज के करेक्ट करूँगी "
        "अच्छा कल से ही शुरू करूँगी"
    )
    assert clauses == []


def test_detect_compound_ignores_two_questions_without_a_transaction():
    """Two queries are nagging, not a financial risk — leave them single-parse."""
    assert detect_compound("Mohan ka kitna udhaar baaki hai aur Sabse zyada udhaar kis ka hai") == []
