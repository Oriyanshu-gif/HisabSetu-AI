"""Money helpers.

All amounts are stored as integer **paise** so no floating point error can ever
touch the ledger. Rupee values are only produced for display or parsing.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

PAISE = Decimal("0.01")


def to_paise(rupees: Decimal | int | float | str) -> int:
    """Convert a rupee amount to integer paise, rounding half-up."""
    value = rupees if isinstance(rupees, Decimal) else Decimal(str(rupees))
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_rupees(paise: int) -> Decimal:
    return (Decimal(paise) / 100).quantize(PAISE)


def indian_group(value: int) -> str:
    """Format a non-negative integer with Indian digit grouping (12,34,567)."""
    text = str(abs(int(value)))
    if len(text) <= 3:
        return text
    head, tail = text[:-3], text[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def format_inr(paise: int, symbol: bool = True) -> str:
    """Format paise as ``₹1,50,000`` or ``₹150.50``."""
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(int(paise)), 100)
    body = indian_group(whole)
    if frac:
        body = f"{body}.{frac:02d}"
    return f"{sign}{'₹' if symbol else ''}{body}"


_HINDI_0_99 = [
    "शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ",
    "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस",
    "बीस", "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाईस", "उनतीस",
    "तीस", "इकतीस", "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस", "सैंतीस", "अड़तीस", "उनतालीस",
    "चालीस", "इकतालीस", "बयालीस", "तैंतालीस", "चवालीस", "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास",
    "पचास", "इक्यावन", "बावन", "तिरपन", "चौवन", "पचपन", "छप्पन", "सत्तावन", "अट्ठावन", "उनसठ",
    "साठ", "इकसठ", "बासठ", "तिरसठ", "चौंसठ", "पैंसठ", "छियासठ", "सड़सठ", "अड़सठ", "उनहत्तर",
    "सत्तर", "इकहत्तर", "बहत्तर", "तिहत्तर", "चौहत्तर", "पचहत्तर", "छिहत्तर", "सतहत्तर", "अठहत्तर", "उन्यासी",
    "अस्सी", "इक्यासी", "बयासी", "तिरासी", "चौरासी", "पचासी", "छियासी", "सत्तासी", "अट्ठासी", "नवासी",
    "नब्बे", "इक्यानवे", "बानवे", "तिरानवे", "चौरानवे", "पचानवे", "छियानवे", "सत्तानवे", "अट्ठानवे", "निन्यानवे",
]

_HINDI_UNITS = ((10_000_000, "करोड़"), (100_000, "लाख"), (1_000, "हज़ार"), (100, "सौ"))


def hindi_int_words(value: int) -> str:
    """Devanagari words for an integer, Indian numbering system."""
    n = int(value)
    if n < 0:
        return "माइनस " + hindi_int_words(-n)
    if n < 100:
        return _HINDI_0_99[n]
    parts: list[str] = []
    for unit_value, unit_name in _HINDI_UNITS:
        if n >= unit_value:
            count, n = divmod(n, unit_value)
            parts.append(f"{_HINDI_0_99[count] if count < 100 else hindi_int_words(count)} {unit_name}")
    if n:
        parts.append(_HINDI_0_99[n])
    return " ".join(parts)


def hindi_rupee_words(paise: int) -> str:
    """Pronounceable Hindi amount, used only for TTS audio."""
    sign = "माइनस " if paise < 0 else ""
    whole, frac = divmod(abs(int(paise)), 100)
    words = f"{hindi_int_words(whole)} रुपये"
    if frac:
        words += f" {_HINDI_0_99[frac]} पैसे"
    return sign + words
