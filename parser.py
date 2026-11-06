"""Deterministic Hindi / Hinglish command parser for KhataVaani.

The parser is intentionally rule based and side-effect free:

* it never touches the database,
* it never guesses a transaction amount,
* its output is auditable (every decision carries a reason code),
* amounts are returned as :class:`decimal.Decimal` rupees and converted to
  integer paise by the ledger service.

Supported amount forms include ``dedh sau`` (150), ``dhai sau`` (250),
``sawa do sau`` (225), ``paune do sau`` (175), ``saade do sau`` (250),
``paanch hazaar`` (5000), ``do hazaar paanch sau`` (2500), ``ek lakh``,
digit forms like ``150``, ``1,500`` and ``₹500`` plus Devanagari numerals.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

INTENT_ADD_CREDIT = "add_credit"
INTENT_RECORD_PAYMENT = "record_payment"
INTENT_BALANCE_QUERY = "balance_query"
INTENT_TOP_DEBTOR = "top_debtor"
INTENT_DAILY_SUMMARY = "daily_summary"
INTENT_UNKNOWN = "unknown"

TRANSACTION_INTENTS = {INTENT_ADD_CREDIT, INTENT_RECORD_PAYMENT}
QUERY_INTENTS = {INTENT_BALANCE_QUERY, INTENT_TOP_DEBTOR, INTENT_DAILY_SUMMARY}
ALL_INTENTS = TRANSACTION_INTENTS | QUERY_INTENTS | {INTENT_UNKNOWN}

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# (value, latin spellings, devanagari spellings)
_NUMBER_TABLE: list[tuple[int, tuple[str, ...], tuple[str, ...]]] = [
    (0, ("shunya", "sifar", "zero"), ("शून्य", "सिफर")),
    (1, ("ek", "eak"), ("एक",)),
    (2, ("do", "dho"), ("दो",)),
    (3, ("teen", "tin"), ("तीन",)),
    (4, ("chaar", "char"), ("चार",)),
    (5, ("paanch", "panch", "paach"), ("पांच", "पाँच")),
    (6, ("chhah", "chhe", "che", "chah"), ("छह", "छः")),
    (7, ("saat", "sat"), ("सात",)),
    (8, ("aath", "ath"), ("आठ",)),
    (9, ("nau",), ("नौ",)),
    (10, ("das", "dus"), ("दस",)),
    (11, ("gyarah", "gyara", "giyarah"), ("ग्यारह",)),
    (12, ("barah", "bara", "baarah"), ("बारह",)),
    (13, ("terah", "tera", "terha"), ("तेरह",)),
    (14, ("chaudah", "chauda", "choudah"), ("चौदह",)),
    (15, ("pandrah", "pandra", "pandraha"), ("पंद्रह", "पन्द्रह")),
    (16, ("solah", "sola"), ("सोलह",)),
    (17, ("satrah", "satra"), ("सत्रह",)),
    (18, ("atharah", "athara", "attharah"), ("अठारह",)),
    (19, ("unnis", "unees"), ("उन्नीस",)),
    (20, ("bees", "bis"), ("बीस",)),
    (21, ("ikkees", "ikees", "ikkees"), ("इक्कीस",)),
    (22, ("baees", "bais", "bayees"), ("बाईस",)),
    (23, ("teis", "teyis", "teyiis"), ("तेईस",)),
    (24, ("chaubees", "chaubis"), ("चौबीस",)),
    (25, ("pachees", "pachchis", "pachis"), ("पच्चीस",)),
    (26, ("chhabbees", "chhabbis", "chabbis"), ("छब्बीस",)),
    (27, ("sattais", "satavis", "sattaees"), ("सत्ताईस",)),
    (28, ("atthais", "athais", "atthaais"), ("अट्ठाईस",)),
    (29, ("untees", "untis", "unatees"), ("उनतीस",)),
    (30, ("tees", "tis"), ("तीस",)),
    (31, ("ikattis", "iktis", "ikattees"), ("इकतीस",)),
    (32, ("battis", "battees"), ("बत्तीस",)),
    (33, ("taintis", "tetis", "taintees"), ("तैंतीस",)),
    (34, ("chauntis", "chautis", "chauntees"), ("चौंतीस",)),
    (35, ("paintis", "paintees"), ("पैंतीस",)),
    (36, ("chhattis", "chhatis", "chhattees"), ("छत्तीस",)),
    (37, ("saintis", "saittis", "saintees"), ("सैंतीस",)),
    (38, ("adhtis", "adatis", "adtees"), ("अड़तीस",)),
    (39, ("untalis", "unchalis", "untalees"), ("उनतालीस",)),
    (40, ("chalis", "chalees"), ("चालीस",)),
    (41, ("iktalis", "ikatalis", "iktalees"), ("इकतालीस",)),
    (42, ("bayalis", "bayalees"), ("बयालीस",)),
    (43, ("taintalis", "taintalees"), ("तैंतालीस",)),
    (44, ("chavalis", "chavalees"), ("चवालीस",)),
    (45, ("paintalis", "paintalees"), ("पैंतालीस",)),
    (46, ("chhiyalis", "chhiyalees"), ("छियालीस",)),
    (47, ("saintalis", "saintalees"), ("सैंतालीस",)),
    (48, ("adhtalis", "adtalis", "adtalees"), ("अड़तालीस",)),
    (49, ("unchas", "unchaas", "unchaas"), ("उनचास",)),
    (50, ("pachaas", "pachas", "pachchaas"), ("पचास",)),
    (51, ("ikyavan", "ikyaavan", "ikyawan"), ("इक्यावन",)),
    (52, ("bavan", "bawan", "baawan"), ("बावन",)),
    (53, ("tirpan", "terpan", "tirpan"), ("तिरपन",)),
    (54, ("chauvan", "chauwan", "chouvan"), ("चौवन",)),
    (55, ("pachpan", "pachapan"), ("पचपन",)),
    (56, ("chhappan", "chappan", "chhappan"), ("छप्पन",)),
    (57, ("sattavan", "satavan", "sattawan"), ("सत्तावन",)),
    (58, ("atthavan", "athavan", "atthawan"), ("अट्ठावन",)),
    (59, ("unsath", "unsaath", "unsat"), ("उनसठ",)),
    (60, ("saath", "saatth"), ("साठ",)),
    (61, ("iksath", "iksat", "iksaath"), ("इकसठ",)),
    (62, ("basath", "basant", "basaath"), ("बासठ",)),
    (63, ("tirsath", "tirsat", "tirsaath"), ("तिरसठ",)),
    (64, ("chausath", "chausat", "chausaath"), ("चौंसठ",)),
    (65, ("pansath", "painsath", "pansaath"), ("पैंसठ",)),
    (66, ("chhiyasath", "chhiyasat", "chhiyasaath"), ("छियासठ",)),
    (67, ("sarsath", "sadsath", "sarsaath"), ("सड़सठ",)),
    (68, ("arsath", "athsath", "arsaath"), ("अड़सठ",)),
    (69, ("unhattar", "unhatar", "unahattar"), ("उनहत्तर",)),
    (70, ("sattar", "satar"), ("सत्तर",)),
    (71, ("ikhattar", "ikahattar", "ikahatar"), ("इकहत्तर",)),
    (72, ("bahattar", "bahatar", "behattar"), ("बहत्तर",)),
    (73, ("tihattar", "tehattar", "tihatar"), ("तिहत्तर",)),
    (74, ("chauhattar", "chauhatar", "chouhattar"), ("चौहत्तर",)),
    (75, ("pachhattar", "pachahattar", "pachhatar"), ("पचहत्तर",)),
    (76, ("chhihattar", "chhihathar", "chhihatar"), ("छिहत्तर",)),
    (77, ("sathattar", "satattar", "satahattar"), ("सतहत्तर",)),
    (78, ("athattar", "athahattar", "athhattar"), ("अठहत्तर",)),
    (79, ("unnyasi", "unyasi", "unnanve"), ("उन्यासी",)),
    (80, ("assi", "asee"), ("अस्सी",)),
    (81, ("ikyasi", "ikyaasi", "ikyasee"), ("इक्यासी",)),
    (82, ("bayasi", "bayaasi", "bayasee"), ("बयासी",)),
    (83, ("tirasi", "tiraasi", "tirasee"), ("तिरासी",)),
    (84, ("chaurasi", "chouraasi", "chaurasee"), ("चौरासी",)),
    (85, ("pachasi", "pachaasi", "pachasee"), ("पचासी",)),
    (86, ("chhiyasi", "chhiyaasi", "chhiyasee"), ("छियासी",)),
    (87, ("sattasi", "sattaasi", "sattasee"), ("सत्तासी",)),
    (88, ("athasi", "atthaasi", "athasee"), ("अट्ठासी",)),
    (89, ("navasi", "navaasi", "navasee"), ("नवासी",)),
    (90, ("nabbe", "nabbey", "nabbe"), ("नब्बे",)),
    (91, ("ikyanve", "ikyaanve", "ikyanave"), ("इक्यानवे",)),
    (92, ("banve", "baanve", "banave"), ("बानवे",)),
    (93, ("tiranve", "tiraanve", "tiranave"), ("तिरानवे",)),
    (94, ("chauranve", "chouraanve", "chauranave"), ("चौरानवे",)),
    (95, ("pachanve", "pachaanve", "pachanave"), ("पचानवे",)),
    (96, ("chhiyanve", "chhiyaanve", "chhiyanave"), ("छियानवे",)),
    (97, ("sattanve", "sattaanve", "sattanave"), ("सत्तानवे",)),
    (98, ("atthanve", "atthaanve", "atthanave"), ("अट्ठानवे",)),
    (99, ("ninyanve", "ninyaanve", "ninyanave"), ("निन्यानवे",)),
]

NUMBER_WORDS: dict[str, int] = {}
for _value, _latin, _devanagari in _NUMBER_TABLE:
    for _word in (*_latin, *_devanagari):
        NUMBER_WORDS.setdefault(_word, _value)

SCALE_WORDS: dict[str, int] = {
    "sau": 100, "so": 100, "सौ": 100,
    "hazaar": 1_000, "hazar": 1_000, "hajaar": 1_000, "hajar": 1_000,
    "हज़ार": 1_000, "हजार": 1_000,
    "lakh": 100_000, "lac": 100_000, "लाख": 100_000,
    "crore": 10_000_000, "karod": 10_000_000, "करोड़": 10_000_000,
}

# (mode, magnitude) — "mult" replaces the following count, "delta" adjusts it.
FRACTION_WORDS: dict[str, tuple[str, Decimal]] = {
    "dedh": ("mult", Decimal("1.5")), "dhedh": ("mult", Decimal("1.5")),
    "डेढ़": ("mult", Decimal("1.5")), "डेढ": ("mult", Decimal("1.5")),
    # Prisma sometimes drops the ढ़ and returns "देद" for "डेढ़" (seen live).
    "देद": ("mult", Decimal("1.5")),
    "dhai": ("mult", Decimal("2.5")), "dhaai": ("mult", Decimal("2.5")), "dhaii": ("mult", Decimal("2.5")),
    "ढाई": ("mult", Decimal("2.5")),
    "sawa": ("delta", Decimal("0.25")), "sava": ("delta", Decimal("0.25")), "sawaa": ("delta", Decimal("0.25")),
    "सवा": ("delta", Decimal("0.25")), "सवाय": ("delta", Decimal("0.25")),
    # Prisma also returns "सावा" with a long आ (seen live on phrase 4).
    "सावा": ("delta", Decimal("0.25")),
    # ...and the nasalised spellings of the same sound.
    "सांवा": ("delta", Decimal("0.25")), "साँवा": ("delta", Decimal("0.25")),
    "सावाँ": ("delta", Decimal("0.25")),
    "saade": ("delta", Decimal("0.5")), "sade": ("delta", Decimal("0.5")), "saadhe": ("delta", Decimal("0.5")),
    "साढ़े": ("delta", Decimal("0.5")), "साढे": ("delta", Decimal("0.5")),
    "paune": ("delta", Decimal("-0.25")), "pone": ("delta", Decimal("-0.25")), "paun": ("delta", Decimal("-0.25")),
    "पौने": ("delta", Decimal("-0.25")), "पौन": ("delta", Decimal("-0.25")),
}

CURRENCY_WORDS = {
    "rupaye", "rupay", "rupee", "rupees", "rupaiya", "rupaiye", "rs", "rupya",
    "रुपये", "रुपए", "रुपया", "रुपयों", "₹",
}

# Words that are never part of a customer name.
NOISE_WORDS = CURRENCY_WORDS | {
    "ka", "ki", "ke", "ko", "ne", "se", "mein", "me", "par", "aur", "ya", "bhi",
    "likh", "likho", "likhdo", "likhde", "likhna", "likhni", "kar", "karo", "karna",
    "de", "do", "dena", "dedo", "dijiye", "dijiye", "diya", "diye", "di", "diyaa",
    "batao", "bata", "bataiye", "batado", "dikhao", "dikha", "dikhaiye",
    "udhaar", "udhar", "credit", "debit", "payment", "paytm", "jama", "wapas", "vapas",
    "balance", "hisaab", "hisab", "summary", "total", "kitna", "kitni", "kitne",
    "kaun", "kis", "kiska", "kiski", "sabse", "zyada", "jyada", "jayada", "top",
    "customer", "customers", "grahak", "ग्राहक", "कस्टमर", "कस्टमरों", "किसका",
    "aaj", "kal", "parso", "abhi", "ab", "subah", "shaam", "raat",
    "please", "plz", "sir", "madam", "bhai", "bhaiya", "ji", "ji.", "ji,",
    "kholo", "khol", "khatam", "confirm", "cancel", "nahi", "haan", "ha", "toh", "to",
    "ka", "ki", "के", "का", "की", "को", "ने", "से", "में", "पर", "और", "या", "भी",
    "लिख", "लिखो", "कर", "करो", "करना", "दे", "दो", "देना", "दीजिए", "दिया", "दिए", "दी",
    "बताओ", "बता", "बताइए", "दिखाओ", "दिखा", "उधार", "क्रेडिट", "पेमेंट", "जमा", "वापस",
    "बैलेंस", "हिसाब", "कितना", "कितनी", "कितने", "कौन", "किस", "किसका", "सबसे",
    "ज़्यादा", "ज्यादा", "आज", "कल", "परसों", "अभी", "सुबह", "शाम", "रात", "जी",
    "कुल", "पूरा", "पूरी", "बाकी", "बकाया", "रिपोर्ट", "खाता", "खाते",
}

_CURRENCY_RE = re.compile(r"(₹|₨|रु\.?|rs\.?|inr)", re.IGNORECASE)
_NUMERIC_RE = re.compile(r"^\d+(?:\.\d{1,2})?$")


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------


@dataclass
class ParsedCommand:
    raw_text: str
    normalized_text: str
    intent: str = INTENT_UNKNOWN
    customer_name: str | None = None
    amount_rupees: Decimal | None = None
    amount_span: str | None = None
    confidence: float = 0.0
    ambiguity: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    executable: bool = False
    is_query: bool = False

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "customer_name": self.customer_name,
            "amount_rupees": None if self.amount_rupees is None else str(self.amount_rupees),
            "amount_span": self.amount_span,
            "confidence": round(self.confidence, 2),
            "ambiguity": list(self.ambiguity),
            "reasons": list(self.reasons),
            "executable": self.executable,
            "is_query": self.is_query,
            "normalized_text": self.normalized_text,
        }


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, split glued digits/words, keep Devanagari."""
    text = unicodedata.normalize("NFC", str(text or ""))
    text = text.translate(_DEVANAGARI_DIGITS)
    text = text.replace("₹", " ₹ ").replace("₨", " ")
    text = text.lower()
    # 1,50,000 / 1,500 -> digits only (before any whitespace insertion)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    # "150rupaye" / "500ka" -> separate tokens
    text = re.sub(r"(?<=[0-9])(?=[^\s0-9.,])", " ", text)
    text = re.sub(r"(?<=[^\s0-9.,])(?=[0-9])", " ", text)
    # Keep Latin, Devanagari (\w alone drops combining matras) and decimal dots.
    text = re.sub(r"[^\w\s.₹\u0900-\u097F]", " ", text, flags=re.UNICODE)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    text = text.replace("_", " ")
    return " ".join(text.split())


def tokenize(text: str) -> list[str]:
    return normalize_text(text).split()


def _drop_verbal_do(tokens: list[str]) -> list[str]:
    """``udhaar likh do`` must not be read as two rupees.

    "do" is both the numeral two and a very common imperative verb. Drop it
    only when it directly follows another verb (likh do / kar do / de do ...).
    """
    verbs = {"likh", "likho", "likhdo", "kar", "karo", "kardo", "de", "dedo",
             "bata", "batao", "batado", "chala", "suno", "rakh", "rakho", "jama",
             "लिख", "लिखो", "कर", "करो", "दे", "बता", "बताओ", "रख", "रखो"}
    out: list[str] = []
    for index, token in enumerate(tokens):
        if token in {"do", "दो"} and index > 0 and tokens[index - 1] in verbs:
            continue
        out.append(token)
    return out


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------


@dataclass
class AmountCandidate:
    value: Decimal
    start: int
    end: int
    span: str
    used_scale: bool


def _apply_fraction(mode: str, magnitude: Decimal, base: Decimal) -> Decimal:
    if mode == "mult":
        return base * magnitude
    return base + magnitude


def _parse_amount_at(tokens: list[str], start: int) -> AmountCandidate | None:
    """Greedy, contiguous Hindi number expression starting at ``start``."""
    i = start
    total = Decimal(0)
    current = Decimal(0)
    pending: tuple[str, Decimal] | None = None
    used_number = False
    used_scale = False

    while i < len(tokens):
        token = tokens[i]

        if token in FRACTION_WORDS:
            if pending is not None:
                break
            pending = FRACTION_WORDS[token]
            i += 1
            continue

        if token in NUMBER_WORDS:
            value = Decimal(NUMBER_WORDS[token])
            if pending is not None:
                value = _apply_fraction(pending[0], pending[1], value)
                pending = None
            current += value
            used_number = True
            i += 1
            continue

        if token in SCALE_WORDS:
            scale = Decimal(SCALE_WORDS[token])
            if pending is not None:
                base = _apply_fraction(pending[0], pending[1], Decimal(1))
                pending = None
                current += base * scale
            elif current == 0:
                current = scale
            else:
                current = current * scale
            used_number = True
            used_scale = True
            if scale >= 1000:
                total += current
                current = Decimal(0)
            i += 1
            continue

        if _NUMERIC_RE.match(token):
            value = Decimal(token)
            if pending is not None:
                value = _apply_fraction(pending[0], pending[1], value)
                pending = None
            current += value
            used_number = True
            i += 1
            continue

        break

    if pending is not None or not used_number:
        return None

    value = total + current
    return AmountCandidate(
        value=value,
        start=start,
        end=i,
        span=" ".join(tokens[start:i]),
        used_scale=used_scale,
    )


def extract_amounts(tokens: list[str]) -> list[AmountCandidate]:
    """Return every contiguous number expression, left to right."""
    candidates: list[AmountCandidate] = []
    i = 0
    while i < len(tokens):
        candidate = _parse_amount_at(tokens, i)
        if candidate is None or candidate.end == candidate.start:
            i += 1
            continue
        candidates.append(candidate)
        i = candidate.end
    return candidates


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

_DAILY_MARKERS = (
    "aaj ka hisaab", "aaj ka hisab", "aaj ka summary", "aaj ki summary",
    "aaj ka total", "aaj ke hisaab", "aaj ke hisab", "daily summary",
    "aaj ka poora hisaab", "aaj ka pura hisaab", "aaj ki report",
    "आज का हिसाब", "आज का हिसाब", "आज का सारांश", "आज की रिपोर्ट",
    "आज का पूरा हिसाब", "आज के हिसाब", "आज का कुल",
)

_TOP_MARKERS = (
    "sabse zyada udhaar", "sabse jyada udhaar", "sabse jayada udhaar",
    "sabse zyada baaki", "sabse jyada baaki", "sabse zyada udhar",
    "top debtor", "top debtors", "top customer", "sabse jada udhaar",
    "kis customer ka sabse zyada", "kiska udhaar sabse zyada",
    "सबसे ज़्यादा उधार", "सबसे ज्यादा उधार", "सबसे ज़्यादा बाकी",
    "सबसे ज्यादा बाकी", "सबसे अधिक उधार", "किसका उधार सबसे ज़्यादा",
)

_QUERY_MARKERS = (
    "kitna udhaar", "kitna udhar", "kitna baaki", "kitni baaki", "kitna bacha",
    "kitna dena", "kitna dena hai", "balance batao", "balance bata", "balance kitna",
    "kitna balance", "hisaab batao", "hisaab bata", "batao kitna", "kitna hisaab",
    "कितना उधार", "कितना बाकी", "कितना बचा", "कितना देना", "बैलेंस बताओ",
    "बैलेंस कितना", "कितना बैलेंस", "हिसाब बताओ",
)

_PAYMENT_STRONG = (
    "wapas", "vapas", "जमा", "jama", "payment", "पेमेंट", "vasool", "वसूल",
    "chuka", "चुका", "chutaya", "चुकाया", "जमा किए", "जमा किया", "jama kiye",
    "jama kiya", "wapas kiye", "wapas kiya", "वापस किए", "वापस किया",
)

_CREDIT_STRONG = (
    "udhaar", "udhar", "उधार", "credit", "क्रेडिट", "baad mein dega",
    "बाद में देगा", "baad me dega", "udhaar likh", "उधार लिख",
)

_PAYMENT_SOFT = ("de diya", "de diye", "de di", "diya", "diye", "दिया", "दिए", "दी")
_CREDIT_SOFT = ("likh do", "likhdo", "likh dena", "likhna", "de do", "dedo",
                "लिख दो", "लिखना", "दे दो", "khate mein", "खाते में")

_GIVE_VERBS = ("de diya", "de diye", "de di", "diya", "diye", "di", "दिया", "दिए", "दी")


def _contains_any(text: str, phrases: tuple[str, ...]) -> str | None:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return None


def detect_intent(text: str, has_amount: bool) -> tuple[str, list[str], list[str], float]:
    """Classify intent using phrase context, not a single keyword.

    Returns ``(intent, reason_codes, human_reasons, confidence)``.
    """
    reasons: list[str] = []
    codes: list[str] = []

    daily_hit = _contains_any(text, _DAILY_MARKERS)
    top_hit = _contains_any(text, _TOP_MARKERS)
    query_hit = _contains_any(text, _QUERY_MARKERS)
    payment_hit = _contains_any(text, _PAYMENT_STRONG)
    credit_hit = _contains_any(text, _CREDIT_STRONG)
    payment_soft = _contains_any(text, _PAYMENT_SOFT)
    credit_soft = _contains_any(text, _CREDIT_SOFT)

    if daily_hit:
        reasons.append(f'"{daily_hit}" se daily summary ka signal mila.')
        return INTENT_DAILY_SUMMARY, codes, reasons, 0.94

    if top_hit:
        reasons.append(f'"{top_hit}" se sabse zyada udhaar ka sawal samajh aaya.')
        return INTENT_TOP_DEBTOR, codes, reasons, 0.93

    transaction_signal = bool(payment_hit or credit_hit or payment_soft or credit_soft)

    if query_hit and has_amount and transaction_signal:
        codes.append("conflicting_intent")
        reasons.append("Ek hi vaaky mein transaction aur balance sawal dono hain.")
        return INTENT_UNKNOWN, codes, reasons, 0.35

    if query_hit:
        reasons.append(f'"{query_hit}" balance ka sawal hai.')
        return INTENT_BALANCE_QUERY, codes, reasons, 0.9

    if payment_hit:
        reasons.append(f'"{payment_hit}" payment/wapas ka pakka signal hai.')
        return INTENT_RECORD_PAYMENT, codes, reasons, 0.93

    if credit_hit:
        # "wapas" wins over "udhaar": "udhaar wapas kar diya" is a payment.
        if payment_hit:
            return INTENT_RECORD_PAYMENT, codes, reasons, 0.9
        reasons.append(f'"{credit_hit}" udhaar dene ka signal hai.')
        return INTENT_ADD_CREDIT, codes, reasons, 0.92

    if payment_soft or credit_soft:
        # Context: who is the subject? "Sunita ne ... diye" = customer paid.
        # "Ramesh ko ... de diye" = shopkeeper gave credit.
        has_ne = re.search(r"(^|\s)(ne|ने)(\s|$)", text) is not None
        has_ko = re.search(r"(^|\s)(ko|को)(\s|$)", text) is not None
        if payment_soft and has_ne and not has_ko:
            reasons.append('Customer "ne" de diya — payment maana gaya.')
            return INTENT_RECORD_PAYMENT, codes, reasons, 0.72
        if credit_soft and has_ko:
            reasons.append('"ko ... de do/likh do" — udhaar dene ka signal.')
            return INTENT_ADD_CREDIT, codes, reasons, 0.7
        if payment_soft and has_ko:
            reasons.append('"ko ... diya" — shopkeeper ne diya, udhaar maana gaya.')
            return INTENT_ADD_CREDIT, codes, reasons, 0.65
        codes.append("unclear_intent")
        reasons.append('"diya/diye" ka matlab context ke bina saaf nahi hai.')
        return INTENT_UNKNOWN, codes, reasons, 0.3

    codes.append("unclear_intent")
    reasons.append("Kaam samajh nahi aaya — udhaar, jama, balance ya summary bolein.")
    return INTENT_UNKNOWN, codes, reasons, 0.2


# ---------------------------------------------------------------------------
# Customer name extraction
# ---------------------------------------------------------------------------

_POSTPOSITIONS = {"ko", "ne", "ka", "ki", "ke", "se", "को", "ने", "का", "की", "के", "से"}

# Honorifics and relationship words are skipped, never taken as the customer
# name: "Ramesh bhai ko ..." must yield "Ramesh", not None.
_HONORIFIC_TOKENS = frozenset(
    {
        "ji", "जी", "sri", "shri", "srimati", "smt", "mr", "mrs",
        "bhai", "bhaiya", "bhaiyya", "didi", "chacha", "chachi", "mausi",
        "bhabhi", "uncle", "aunty", "sir", "madam",
        "भाई", "भैया", "दीदी", "चाचा", "चाची", "मौसी", "भाभी", "सर", "मैडम",
    }
)


def _is_name_token(token: str, allow_numbers: bool = False) -> bool:
    if not token or token in NOISE_WORDS:
        return False
    if token in SCALE_WORDS or token in FRACTION_WORDS:
        return False
    if not allow_numbers and token in NUMBER_WORDS:
        return False
    if any(char.isdigit() for char in token):
        return False
    if len(token) < 2:
        return False
    return bool(re.search(r"[a-zA-Z\u0900-\u097F]", token))


def _clean_name(tokens: list[str], allow_numbers: bool = False) -> str | None:
    words = [token for token in tokens if _is_name_token(token, allow_numbers)]
    if not words:
        return None
    words = words[:4]
    rendered = []
    for word in words:
        if re.search(r"[\u0900-\u097F]", word):
            rendered.append(word)
        else:
            rendered.append(word[:1].upper() + word[1:])
    return " ".join(rendered)


def _leading_name_span(tokens: list[str]) -> tuple[str | None, int]:
    """Customer name opening the sentence, before the first ``ko`` / ``ne``.

    A customer name can itself be a number word (``Das``, ``Sat Pal``), which
    otherwise collides with amount extraction. When the text before the first
    postposition sits at the start of the sentence, spans at most three tokens
    and carries no digits, scale or fraction words, treat it as the name and
    hand back the index from which amount extraction may proceed.

    Returns ``(name, amount_start_floor)``; ``(None, 0)`` when it does not apply.
    """
    end = None
    for index, token in enumerate(tokens):
        if token in {"ko", "ne", "को", "ने"}:
            end = index
            break
    if end is None or end == 0 or end > 3:
        return None, 0

    prefix = tokens[:end]
    for token in prefix:
        if any(char.isdigit() for char in token):
            return None, 0
        if token in SCALE_WORDS or token in FRACTION_WORDS:
            return None, 0

    name = _clean_name([t for t in prefix if t not in _HONORIFIC_TOKENS],
                       allow_numbers=True)
    if not name:
        return None, 0
    return name, end


def extract_customer_name(tokens: list[str], amount_start: int | None = None,
                          amount_end: int | None = None) -> str | None:
    """Heuristic customer name lookup before the ledger resolves it."""
    honorifics = _HONORIFIC_TOKENS

    # 1. "Ramesh ke naam" / "रमेश के नाम"
    for index, token in enumerate(tokens):
        if token in {"naam", "नाम"} and index >= 2 and tokens[index - 1] in {"ke", "के"}:
            collected: list[str] = []
            cursor = index - 2
            while cursor >= 0 and len(collected) < 4:
                if tokens[cursor] in honorifics:
                    cursor -= 1
                    continue
                if _is_name_token(tokens[cursor]):
                    collected.insert(0, tokens[cursor])
                    cursor -= 1
                    continue
                break
            name = _clean_name(collected)
            if name:
                return name

    # 2. Words before the first postposition: "Ramesh ko...", "Mohan ka..."
    for index, token in enumerate(tokens):
        if token in _POSTPOSITIONS:
            collected = []
            cursor = index - 1
            while cursor >= 0 and len(collected) < 4:
                if tokens[cursor] in honorifics:
                    cursor -= 1
                    continue
                if _is_name_token(tokens[cursor]):
                    collected.insert(0, tokens[cursor])
                    cursor -= 1
                    continue
                break
            name = _clean_name(collected)
            if name:
                return name
            break

    # 3. Before / after the amount: "Ramesh 150 udhaar", "500 Ramesh ko"
    if amount_start is not None and amount_end is not None:
        prefix = tokens[:amount_start]
        collected = []
        for token in reversed(prefix):
            if _is_name_token(token):
                collected.insert(0, token)
                if len(collected) >= 3:
                    break
                continue
            break
        name = _clean_name(collected)
        if name:
            return name
        suffix = tokens[amount_end:]
        collected = []
        for token in suffix:
            if _is_name_token(token):
                collected.append(token)
                if len(collected) >= 3:
                    break
                continue
            break
        name = _clean_name(collected)
        if name:
            return name

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def detect_hint_needs_amount(text: str) -> bool:
    """True when the utterance is action-like and therefore needs an amount."""
    markers = _CREDIT_STRONG + _PAYMENT_STRONG + (
        "udhaar", "udhar", "jama", "wapas", "credit", "payment",
        "उधार", "जमा", "वापस", "क्रेडिट", "पेमेंट",
    )
    return any(marker in text for marker in markers)


_DE_WORDS = {"de", "दे"}
_DO_WORDS = {"do", "दो"}


def _repair_stt_dedh(tokens: list[str]) -> tuple[list[str], bool]:
    """Prisma often hears "dedh" (1.5) as "de do". "de do" directly followed by a scale word
    (sau/hazaar/lakh) is not a natural imperative (Hindi puts the amount before the verb:
    "sau rupaye de do"), so treat it as "dedh" and report that we assumed it."""
    out, repaired, index = [], False, 0
    while index < len(tokens):
        is_de_do = (index + 2 < len(tokens) and tokens[index] in _DE_WORDS
                    and tokens[index + 1] in _DO_WORDS and tokens[index + 2] in SCALE_WORDS)
        previous = out[-1] if out else ""
        previous_is_number = (previous in NUMBER_WORDS or previous in SCALE_WORDS
                              or previous in FRACTION_WORDS or any(c.isdigit() for c in previous))
        if is_de_do and not previous_is_number:
            out.append("dedh"); repaired = True; index += 2; continue
        out.append(tokens[index]); index += 1
    return out, repaired


_COMPOUND_SPLIT_RE = re.compile(
    r"\s*(?:;|\n|,\s*|\s+(?:aur|और|phir|फिर|and|then)\s+)\s*",
    re.IGNORECASE,
)


def detect_compound(text: str) -> list[tuple[str, "ParsedCommand"]]:
    """Split a multi-clause utterance into separately actionable commands.

    One utterance, two instructions ("Ramesh ko sau ka udhaar likh do aur
    Sunita ne do sau wapas diye") used to be reduced to a single action:
    either a multiple-amount clarification or, worse, only the second half
    (`Aaj ka hisaab batao aur ...` silently dropped the credit).

    This is *detection only* — the caller still parses the whole utterance for
    the normal path and asks the shopkeeper to say one command at a time.  It
    returns a non-empty list only when

    * at least two clauses carry a recognisable intent, and
    * at least one clause is a financial transaction.

    Filler joined by "aur"/"और" (as in the noisy STT fixtures) parses to
    ``unknown`` and therefore never triggers this.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    clauses = [part.strip() for part in _COMPOUND_SPLIT_RE.split(raw) if part and part.strip()]
    if len(clauses) < 2:
        return []

    parsed_clauses: list[tuple[str, ParsedCommand]] = []
    for clause in clauses:
        if len(clause) < 4:
            continue
        parsed = parse_command(clause)
        if parsed.intent == INTENT_UNKNOWN:
            continue
        parsed_clauses.append((clause, parsed))

    if len(parsed_clauses) < 2:
        return []
    has_transaction = any(p.intent in TRANSACTION_INTENTS for _c, p in parsed_clauses)
    if not has_transaction:
        # Two questions in one breath: not a financial instruction, so we keep
        # the existing single-parse behaviour instead of nagging the speaker.
        return []
    return parsed_clauses


def parse_command(text: str) -> ParsedCommand:
    """Parse a Hindi/Hinglish ledger instruction. Pure function, no I/O."""
    tokens, assumed_dedh = _repair_stt_dedh(tokenize(text))
    amount_tokens = _drop_verbal_do(tokens)
    # A name that opens the sentence may itself be a number word ("Das ko ...").
    leading_name, leading_floor = _leading_name_span(amount_tokens)
    candidates = extract_amounts(amount_tokens)
    if leading_floor:
        candidates = [c for c in candidates if c.start >= leading_floor]

    result = ParsedCommand(raw_text=str(text or ""), normalized_text=" ".join(tokens))
    if assumed_dedh:
        result.ambiguity.append("assumed_dedh")
        result.reasons.append('Transcript mein "de do sau" tha; "dedh sau" maana gaya. Amount check karein.')

    chosen: AmountCandidate | None = None
    if len(candidates) > 1:
        result.ambiguity.append("multiple_amounts")
        result.reasons.append("Ek se zyada amount mile — kaunsa sahi hai?")
    elif len(candidates) == 1:
        chosen = candidates[0]
        result.amount_rupees = chosen.value
        result.amount_span = chosen.span
        if chosen.value <= 0:
            result.ambiguity.append("invalid_amount")
            result.reasons.append("Amount zero se bada hona chahiye.")
            result.amount_rupees = None
        elif chosen.value > Decimal("10000000"):
            result.ambiguity.append("invalid_amount")
            result.reasons.append("Amount ek crore se zyada nahi ho sakta.")
            result.amount_rupees = None
        elif chosen.value != chosen.value.to_integral_value() and chosen.value.as_tuple().exponent < -2:
            result.ambiguity.append("invalid_amount")
            result.reasons.append("Amount mein do se zyada decimal nahi ho sakte.")
            result.amount_rupees = None

    amount_start = chosen.start if chosen else None
    amount_end = chosen.end if chosen else None
    result.customer_name = (
        leading_name
        if leading_name
        else extract_customer_name(tokens, amount_start, amount_end)
    )

    has_amount = result.amount_rupees is not None
    intent, codes, reasons, intent_confidence = detect_intent(result.normalized_text, has_amount)
    result.intent = intent
    result.ambiguity.extend(code for code in codes if code not in result.ambiguity)
    result.reasons.extend(reasons)
    result.confidence = intent_confidence
    result.is_query = intent in QUERY_INTENTS

    if intent in TRANSACTION_INTENTS:
        if len(candidates) > 1:
            result.ambiguity.append("amount_needs_review")
        elif not has_amount and not ({"invalid_amount", "multiple_amounts"} & set(result.ambiguity)):
            result.ambiguity.append("missing_amount")
        if not result.customer_name:
            result.ambiguity.append("missing_customer")
            result.reasons.append("Customer ka naam saaf nahi mila.")

        if has_amount and result.customer_name and len(candidates) == 1:
            result.confidence = min(0.98, intent_confidence + 0.04)
        elif not has_amount:
            result.confidence = min(result.confidence, 0.55)
        else:
            result.confidence = min(result.confidence, 0.6)

        result.executable = (
            has_amount
            and bool(result.customer_name)
            and len(candidates) == 1
            and "conflicting_intent" not in result.ambiguity
        )
    elif intent in QUERY_INTENTS:
        result.confidence = max(result.confidence, 0.8)
        if intent == INTENT_BALANCE_QUERY and not result.customer_name:
            result.ambiguity.append("missing_customer")
            result.reasons.append("Kis customer ka balance? Naam bata dein.")
        result.executable = False
    else:
        result.executable = False

    # Stable, de-duplicated reason list
    result.ambiguity = list(dict.fromkeys(result.ambiguity))
    result.reasons = list(dict.fromkeys(result.reasons))
    return result


# ---------------------------------------------------------------------------
# Name normalisation / matching helpers (used by the ledger service)
# ---------------------------------------------------------------------------

_DEVANAGARI_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "ळ": "l", "क़": "q",
    "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f",
}
_DEVANAGARI_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo",
    "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
_DEVANAGARI_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ँ": "n",
    "ः": "h", "्": "",
}


def transliterate_devanagari(text: str) -> str:
    """Best-effort Devanagari -> Latin transliteration for name matching only."""
    out: list[str] = []
    characters = list(text)
    index = 0
    while index < len(characters):
        char = characters[index]
        if char in _DEVANAGARI_CONSONANTS:
            out.append(_DEVANAGARI_CONSONANTS[char])
            nxt = characters[index + 1] if index + 1 < len(characters) else ""
            if nxt == "्":
                index += 2
                continue
            if nxt in _DEVANAGARI_MATRAS:
                out.append(_DEVANAGARI_MATRAS[nxt])
                index += 2
                continue
            # A consonant at the very end of a word has no inherent vowel:
            # रमेश -> ramesh (not ramesha).
            if nxt == "" or nxt.isspace():
                index += 1
                continue
            out.append("a")
            index += 1
            continue
        if char in _DEVANAGARI_VOWELS:
            out.append(_DEVANAGARI_VOWELS[char])
            index += 1
            continue
        if char in _DEVANAGARI_MATRAS:
            out.append(_DEVANAGARI_MATRAS[char])
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def simplify_latin(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)
    text = text.replace("aa", "a").replace("ee", "i").replace("oo", "u")
    text = text.replace("ph", "f").replace("w", "v")
    return " ".join(text.split())


# Trailing honorifics a speaker adds to a customer name.  Stripped only when
# at least one other token remains, so a customer literally called "Bhai" still
# gets a usable key.
_HONORIFICS = {"ji", "sri", "shri", "mr", "mrs", "ms", "smt", "bhai"}


def _strip_honorifics(text: str) -> str:
    """Drop trailing honorifics, keeping at least one token.

    Run on the *folded* text as well: transliteration writes "जी" as "jee" and
    "भाई" as "bhaai", which only become "ji"/"bhai" after ``simplify_latin``.
    """
    tokens = text.split()
    kept = [token for token in tokens if token not in _HONORIFICS]
    if not kept:  # every token was an honorific — keep the original wording
        return " ".join(tokens)
    return " ".join(kept)


def normalize_name(name: str) -> str:
    """Normalise a name for exact matching (case, punctuation, honorifics)."""
    text = unicodedata.normalize("NFC", str(name or "")).lower()
    text = transliterate_devanagari(text) if re.search(r"[\u0900-\u097F]", text) else text
    text = re.sub(r"[^a-z\s]", " ", text)
    return _strip_honorifics(" ".join(text.split()))


def canonical_name(name: str) -> str:
    """Ledger comparison key for a customer name.

    Same person, three writings: ``Sunita`` (typed), ``सुनीता`` (Prisma always
    returns Devanagari for a Hindi phrase) and ``Ramesh bhai`` (speaker added an
    honorific).  ``normalize_name`` alone maps ``सुनीता`` -> ``suneetaa`` and
    leaves ``bhai``, so an exact-string match against ``Sunita`` failed and the
    person could end up with two ledger rows.  Folding through ``simplify_latin``
    makes both spellings collapse to ``sunita`` / ``ramesh``.

    The fuzzy path (``name_similarity``, ``_matches_from_text``) already folded
    this way; this helper is the same fold exposed for exact matching, duplicate
    detection and the evaluation's customer comparison.
    """
    return _strip_honorifics(simplify_latin(normalize_name(name)))


def name_similarity(first: str, second: str) -> float:
    a = canonical_name(first)
    b = canonical_name(second)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    # Partial containment helps with "Ramesh" vs "Ramesh Kumar"
    if a in b or b in a:
        shorter = min(len(a), len(b))
        ratio = max(ratio, 0.86 + 0.14 * (shorter / max(len(a), len(b))))
    return round(ratio, 3)
