"""Per-language number vocabulary for the ten voice languages.

Every table here is *data*, not logic: :func:`parser._parse_amount_at` composes
these the same way it composes the Hindi table, so ``পঞ্চাশ``, ``ஐம்பது`` and
``ਪੰਜਾਹ`` are all "fifty" to one algorithm.

Spellings come from two places:

* the language itself (units, tens, hundreds, thousand/lakh/crore, and the
  half/one-and-a-half/two-and-a-half forms each language actually uses), and
* real Prisma Prisma ``verbatim`` transcripts — the provider writes amounts in
  its own spelling, and the aliases below are the spellings it has been seen to
  produce (see ``docs/lang-eval.md`` and ``eval_langs.py``).

Romanised aliases are included because shopkeepers often type what they say in
Latin script, and because an English-language STT pass returns Latin words.
"""

from __future__ import annotations

from decimal import Decimal

# (value, aliases)
NumTable = dict[int, tuple[str, ...]]
FractionTable = dict[str, tuple[str, "Decimal"]]
ScaleTable = dict[int, tuple[str, ...]]


def _numbers(*rows: tuple[int, str]) -> dict[str, int]:
    """``(1, "एक ek")`` -> ``{"एक": 1, "ek": 1}``."""
    table: dict[str, int] = {}
    for value, words in rows:
        for word in words.split():
            table.setdefault(word, value)
    return table


def _scales(*rows: tuple[int, str]) -> dict[str, int]:
    return _numbers(*rows)


def _fractions(*rows: tuple[str, str, str]) -> dict[str, tuple[str, Decimal]]:
    """``("दीड", "mult", "1.5")`` -> ``{"दीड": ("mult", Decimal("1.5"))}``."""
    table: dict[str, tuple[str, Decimal]] = {}
    for words, mode, magnitude in rows:
        for word in words.split():
            table.setdefault(word, (mode, Decimal(magnitude)))
    return table


# ---------------------------------------------------------------------------
# English (en-IN)
# ---------------------------------------------------------------------------
# en-IN shares the Hinglish parser, so these are merged into the Hindi tables:
# "dedh sau" and "one hundred fifty" are both valid in the same sentence.

EN_NUMBERS = _numbers(
    (0, "zero"),
    (1, "one"),
    (2, "two"),
    (3, "three"),
    (4, "four"),
    (5, "five"),
    (6, "six"),
    (7, "seven"),
    (8, "eight"),
    (9, "nine"),
    (10, "ten"),
    (11, "eleven"),
    (12, "twelve"),
    (13, "thirteen"),
    (14, "fourteen"),
    (15, "fifteen"),
    (16, "sixteen"),
    (17, "seventeen"),
    (18, "eighteen"),
    (19, "nineteen"),
    (20, "twenty"),
    (30, "thirty"),
    (40, "forty fourty"),
    (50, "fifty"),
    (60, "sixty"),
    (70, "seventy"),
    (80, "eighty"),
    (90, "ninety"),
)
EN_SCALES = _scales(
    (100, "hundred"),
    (1000, "thousand"),
    (100000, "lakh lac"),
    (10000000, "crore"),
)
# English says its halves in words ("one thousand five hundred"), so the
# fraction table stays empty rather than inventing a single-word form.
EN_FRACTIONS: FractionTable = {}

# ---------------------------------------------------------------------------
# Marathi
# ---------------------------------------------------------------------------

MR_NUMBERS = _numbers(
    (0, "शून्य shunya"),
    (1, "एक ek"),
    (2, "दोन don"),
    (3, "तीन teen"),
    (4, "चार char"),
    (5, "पाच pach"),
    (6, "सहा saha"),
    (7, "सात saat"),
    (8, "आठ aath"),
    (9, "नऊ nau"),
    (10, "दहा daha"),
    (11, "अकरा akra"),
    (12, "बारा bara"),
    (13, "तेरा tera"),
    (14, "चौदा chauda"),
    (15, "पंधरा pandhra"),
    (16, "सोळा sola"),
    (17, "सतरा satra"),
    (18, "अठरा athra"),
    (19, "एकोणीस ekonis"),
    (20, "वीस vis vees"),
    (21, "एकवीस ekvis"),
    (25, "पंचवीस panchvis"),
    (30, "तीस tis"),
    (35, "पस्तीस pastis"),
    (40, "चाळीस chalis"),
    (45, "पंचेचाळीस panchechalis"),
    (50, "पन्नास pannas"),
    (55, "पंचावन्न panchavann"),
    (60, "साठ saath"),
    (65, "पासष्ट pasasht"),
    (70, "सत्तर sattar"),
    (75, "पंच्याहत्तर panchyahattar"),
    (80, "ऐंशी ainshi"),
    (85, "पंच्याऐंशी panchyaainshi"),
    (90, "नव्वद navvad"),
    (95, "पंच्याण्णव panchyannav"),
    (100, "शंभर shambhar एकशे ekshe"),
    (200, "दोनशे donashe"),
    (300, "तीनशे tinashe"),
    (400, "चारशे charashe"),
    (500, "पाचशे pachashe"),
    (600, "सहाशे sahashe"),
    (700, "सातशे saatashe"),
    (800, "आठशे aathashe"),
    (900, "नऊशे naushe"),
)
MR_SCALES = _scales(
    (100, "शे she"),
    (1000, "हजार hajar hazaar"),
    (100000, "लाख lakh"),
    (10000000, "कोटी koti"),
)
MR_FRACTIONS = _fractions(
    ("दीड deedh did", "mult", "1.5"),
    ("अडीच adich", "mult", "2.5"),
    ("सव्वा savva", "delta", "0.25"),
    ("पावणे pavne", "delta", "-0.25"),
    ("साडे sade", "delta", "0.5"),
)

# ---------------------------------------------------------------------------
# Gujarati
# ---------------------------------------------------------------------------

GU_NUMBERS = _numbers(
    (0, "શૂન્ય shunya"),
    (1, "એક ek"),
    (2, "બે be"),
    (3, "ત્રણ tran"),
    (4, "ચાર char"),
    (5, "પાંચ panch pach"),
    (6, "છ chha"),
    (7, "સાત saat"),
    (8, "આઠ aath"),
    (9, "નવ nav"),
    (10, "દસ das"),
    (11, "અગિયાર agiyar"),
    (12, "બાર bar"),
    (13, "તેર ter"),
    (14, "ચૌદ chaud"),
    (15, "પંદર pandar"),
    (16, "સોળ sol"),
    (17, "સત્તર sattar"),
    (18, "અઢાર adhar"),
    (19, "ઓગણીસ oganis"),
    (20, "વીસ vis vees"),
    (21, "એકવીસ ekvis"),
    (25, "પચ્ચીસ pachchis"),
    (30, "ત્રીસ tris"),
    (35, "પાંત્રીસ pantris"),
    (40, "ચાલીસ chalis"),
    (45, "પિસ્તાલીસ pistalis"),
    (50, "પચાસ pachas"),
    (55, "પંચાવન panchavan"),
    (60, "સાઠ sath"),
    (65, "પાંસઠ pansath"),
    (70, "સિત્તેર sitter"),
    (75, "પંચોતેર panchoter"),
    (80, "એંસી ensi"),
    (85, "પંચ્યાસી panchyasi"),
    (90, "નેવું nevu"),
    (95, "પંચાણું panchanu"),
    (100, "સો so એકસો ekso"),
    (200, "બસો baso બેસો beso"),
    (300, "ત્રણસો transo"),
    (400, "ચારસો charso"),
    (500, "પાંચસો panchso"),
    (600, "છસો chhaso"),
    (700, "સાતસો saatso"),
    (800, "આઠસો aathso"),
    (900, "નવસો navso"),
)
GU_SCALES = _scales(
    (100, "સો so"),
    (1000, "હજાર hajar hazaar"),
    (100000, "લાખ lakh"),
    (10000000, "કરોડ karod"),
)
GU_FRACTIONS = _fractions(
    ("દોઢ dodh", "mult", "1.5"),
    ("અઢી adhi", "mult", "2.5"),
    ("સવા sava", "delta", "0.25"),
    ("પોણા pona", "delta", "-0.25"),
    ("સાડા sada", "delta", "0.5"),
)

# ---------------------------------------------------------------------------
# Punjabi
# ---------------------------------------------------------------------------

PA_NUMBERS = _numbers(
    (0, "ਸਿਫ਼ਰ sifar ਸ਼ੂਨਯ shunya"),
    (1, "ਇੱਕ ik ek"),
    (2, "ਦੋ do"),
    (3, "ਤਿੰਨ tin teen"),
    (4, "ਚਾਰ char"),
    (5, "ਪੰਜ panj"),
    (6, "ਛੇ chhe"),
    (7, "ਸੱਤ satt"),
    (8, "ਅੱਠ atth"),
    (9, "ਨੌਂ nau"),
    (10, "ਦਸ das"),
    (11, "ਗਿਆਰਾਂ giyaran"),
    (12, "ਬਾਰਾਂ baran"),
    (13, "ਤੇਰਾਂ teran"),
    (14, "ਚੌਦਾਂ chaudan"),
    (15, "ਪੰਦਰਾਂ pandran"),
    (16, "ਸੋਲਾਂ solan"),
    (17, "ਸਤਾਰਾਂ sataran"),
    (18, "ਅਠਾਰਾਂ atharan"),
    (19, "ਉੱਨੀ unni"),
    (20, "ਵੀਹ vih"),
    (21, "ਇੱਕੀ ikki"),
    (25, "ਪੱਚੀ pachchi"),
    (30, "ਤੀਹ tih"),
    (35, "ਪੈਂਤੀ painti"),
    (40, "ਚਾਲੀ chali"),
    (45, "ਪੰਤਾਲੀ pantali"),
    (50, "ਪੰਜਾਹ panjah"),
    (55, "ਪਚਵੰਜਾ pachvanja"),
    (60, "ਸੱਠ satth"),
    (65, "ਪੈਂਝੜ painjharh"),
    (70, "ਸੱਤਰ sattar"),
    (75, "ਪੰਝੱਤਰ panjhattar"),
    (80, "ਅੱਸੀ assi"),
    (85, "ਪਚਾਸੀ pachasi"),
    (90, "ਨੱਬੇ nabbe"),
    (95, "ਪਚਾਨਵੇਂ pachanven"),
    (100, "ਸੌ sau ਸੈਂ sain"),
    (200, "ਦੋਸੌ dosau"),
    (300, "ਤਿੰਨਸੌ tinsau"),
    (400, "ਚਾਰਸੌ charsau"),
    (500, "ਪੰਜਸੌ panjsau"),
    (600, "ਛੇਸੌ chhesau"),
    (700, "ਸੱਤਸੌ sattsau"),
    (800, "ਅੱਠਸੌ atthsau"),
    (900, "ਨੌਂਸੌ nausau"),
)
PA_SCALES = _scales(
    (100, "ਸੌ sau ਸੈਂ sain"),
    (1000, "ਹਜ਼ਾਰ hajar hazaar ਹਜਾਰ"),
    (100000, "ਲੱਖ lakh"),
    (10000000, "ਕਰੋੜ karod"),
)
PA_FRACTIONS = _fractions(
    ("ਡੇਢ dedh", "mult", "1.5"),
    ("ਢਾਈ dhai", "mult", "2.5"),
    ("ਸਵਾ sava", "delta", "0.25"),
    ("ਪੌਣੇ paune", "delta", "-0.25"),
    ("ਸਾਢੇ sadhe", "delta", "0.5"),
)

# ---------------------------------------------------------------------------
# Bengali
# ---------------------------------------------------------------------------

BN_NUMBERS = _numbers(
    (0, "শূন্য shunno"),
    (1, "এক ek ekh"),
    (2, "দুই dui"),
    (3, "তিন tin teen"),
    (4, "চার char"),
    (5, "পাঁচ pach panch"),
    (6, "ছয় chhoy choy"),
    (7, "সাত saat sat"),
    (8, "আট aat at"),
    (9, "নয় noy"),
    (10, "দশ dosh dash"),
    (11, "এগারো egaro"),
    (12, "বারো baro"),
    (13, "তেরো tero"),
    (14, "চৌদ্দ chouddo"),
    (15, "পনেরো ponero"),
    (16, "ষোলো sholo"),
    (17, "সতেরো shotero"),
    (18, "আঠারো atharo"),
    (19, "উনিশ unish"),
    (20, "বিশ bish"),
    (21, "একুশ ekush"),
    (25, "পঁচিশ ponchish"),
    (30, "ত্রিশ trish"),
    (35, "পঁয়ত্রিশ poyotrish"),
    (40, "চল্লিশ chollish"),
    (45, "পঁয়তাল্লিশ poytallish"),
    (50, "পঞ্চাশ ponchash panchash"),
    (55, "পঞ্চান্ন ponchanno"),
    (60, "ষাট shat"),
    (65, "পঁয়ষট্টি poyshotti"),
    (70, "সত্তর shottor"),
    (75, "পঁচাত্তর ponchattor"),
    (80, "আশি ashi"),
    (85, "পঁচাশি ponchashi"),
    (90, "নব্বই nobboi"),
    (95, "পঁচানব্বই ponchanobboi"),
    (100, "একশো eksho একশ eksh"),
    (200, "দুইশো duisho দুশো dusho"),
    (300, "তিনশো tinsho"),
    (400, "চারশো charsho"),
    (500, "পাঁচশো panchsho"),
    (600, "ছয়শো chhoysho"),
    (700, "সাতশো satsho"),
    (800, "আটশো atsho"),
    (900, "নয়শো noysho"),
)
BN_SCALES = _scales(
    (100, "শো sho শত shoto"),
    (1000, "হাজার hazar hajaar"),
    (100000, "লাখ lakh লক্ষ lokkho"),
    (10000000, "কোটি koti"),
)
BN_FRACTIONS = _fractions(
    ("দেড় derh দেড়ে", "mult", "1.5"),
    ("আড়াই arai", "mult", "2.5"),
    ("সোয়া shoa", "delta", "0.25"),
    ("পৌনে poune", "delta", "-0.25"),
    ("সাড়ে sare", "delta", "0.5"),
)

# ---------------------------------------------------------------------------
# Kannada
# ---------------------------------------------------------------------------

KN_NUMBERS = _numbers(
    (0, "ಸೊನ್ನೆ sonne"),
    (1, "ಒಂದು ondu"),
    (2, "ಎರಡು eradu"),
    (3, "ಮೂರು mooru muru"),
    (4, "ನಾಲ್ಕು nalku"),
    (5, "ಐದು aidu"),
    (6, "ಆರು aaru"),
    (7, "ಏಳು elu"),
    (8, "ಎಂಟು entu"),
    (9, "ಒಂಬತ್ತು ombattu"),
    (10, "ಹತ್ತು hattu"),
    (11, "ಹನ್ನೊಂದು hannondu"),
    (12, "ಹನ್ನೆರಡು hanneradu"),
    (13, "ಹದಿಮೂರು hadimooru"),
    (14, "ಹದಿನಾಲ್ಕು hadinalku"),
    (15, "ಹದಿನೈದು hadinaidu"),
    (16, "ಹದಿನಾರು hadinaaru"),
    (17, "ಹದಿನೇಳು hadinelu"),
    (18, "ಹದಿನೆಂಟು hadinentu"),
    (19, "ಹತ್ತೊಂಬತ್ತು hattombattu"),
    (20, "ಇಪ್ಪತ್ತು ippattu"),
    (25, "ಇಪ್ಪತ್ತೈದು ippattu aidu"),
    (30, "ಮೂವತ್ತು moovattu"),
    (40, "ನಲವತ್ತು nalavattu"),
    (50, "ಐವತ್ತು aivattu"),
    (60, "ಅರವತ್ತು aravattu"),
    (70, "ಎಪ್ಪತ್ತು eppattu"),
    (80, "ಎಂಬತ್ತು embattu"),
    (90, "ತೊಂಬತ್ತು tombattu"),
    (100, "ನೂರು nooru"),
    (200, "ಇನ್ನೂರು innooru ಇನ್ನೂರ innoora"),
    (300, "ಮುನ್ನೂರು munnooru ಮುನ್ನೂರ munnoora"),
    (400, "ನಾನ್ನೂರು nannooru ನಾನ್ನೂರ nannoora"),
    (500, "ಐನೂರು ainooru ಐನೂರ ainoora"),
    (600, "ಆರುನೂರು aarunooru ಆರುನೂರ aarunoora"),
    (700, "ಏಳುನೂರು elunooru ಏಳುನೂರ elunoora"),
    (800, "ಎಂಟುನೂರು entunooru ಎಂಟುನೂರ entunoora"),
    (900, "ಒಂಬೈನೂರು ombainooru ಒಂಬೈನೂರ ombainoora"),
)
KN_SCALES = _scales(
    (100, "ನೂರ noora"),
    (1000, "ಸಾವಿರ savira ಸಾವಿರದ savirada"),
    (100000, "ಲಕ್ಷ lakhsha laksha"),
    (10000000, "ಕೋಟಿ koti"),
)
KN_FRACTIONS = _fractions(
    ("ಒಂದೂವರೆ onduvare", "mult", "1.5"),
    ("ಎರಡೂವರೆ eraduvere", "mult", "2.5"),
    ("ಕಾಲು kaalu", "delta", "0.25"),
    ("ಮುಕ್ಕಾಲು mukkalu", "delta", "-0.25"),
)

# ---------------------------------------------------------------------------
# Malayalam
# ---------------------------------------------------------------------------

ML_NUMBERS = _numbers(
    (0, "പൂജ്യം poojyam"),
    (1, "ഒന്ന് onnu ഒരു oru"),
    (2, "രണ്ട് randu"),
    (3, "മൂന്ന് moonnu"),
    (4, "നാല് naalu"),
    (5, "അഞ്ച് anchu"),
    (6, "ആറ് aaru"),
    (7, "ഏഴ് eazhu"),
    (8, "എട്ട് ettu"),
    (9, "ഒമ്പത് ombatu"),
    (10, "പത്ത് pattu"),
    (11, "പതിനൊന്ന് pathinonnu"),
    (12, "പന്ത്രണ്ട് pantrandu"),
    (13, "പതിമൂന്ന് pathimoonnu"),
    (14, "പതിനാല് pathinaalu"),
    (15, "പതിനഞ്ച് pathinanchu"),
    (16, "പതിനാറ് pathinaaru"),
    (17, "പതിനേഴ് pathineazhu"),
    (18, "പതിനെട്ട് pathinettu"),
    (19, "പത്തൊമ്പത് pattombatu"),
    (20, "ഇരുപത് irupathu"),
    (25, "ഇരുപത്തിയഞ്ച് irupathiyanchu"),
    (30, "മുപ്പത് muppathu"),
    (40, "നാല്പത് naalpathu"),
    (50, "അമ്പത് ampathu"),
    (60, "അറുപത് arupathu"),
    (70, "എഴുപത് ezhupathu"),
    (80, "എൺപത് enpathu"),
    (90, "തൊണ്ണൂറ് thonnooru"),
    (100, "നൂറ് nooru"),
    (150, "നൂറ്റമ്പത് noottampathu"),
    (200, "ഇരുന്നൂറ് irunnooru"),
    (250, "ഇരുന്നൂറ്റമ്പത് irunnoottampathu"),
    (300, "മുന്നൂറ് munnooru"),
    (400, "നാനൂറ് naanooru"),
    (500, "അഞ്ഞൂറ് anjnooru"),
    (600, "അറുനൂറ് arunooru"),
    (700, "എഴുനൂറ് ezhunooru"),
    (800, "എണ്ണൂറ് ennooru"),
    (900, "തൊള്ളായിരം thollayiram"),
)
ML_SCALES = _scales(
    (100, "നൂറ്റി nootti"),
    (1000, "ആയിരം aayiram ആയിരത്തി aayirathi"),
    (100000, "ലക്ഷം laksham ലക്ഷ lakhsha"),
    (10000000, "കോടി koti"),
)
ML_FRACTIONS = _fractions(
    ("ഒന്നര onnara", "mult", "1.5"),
    ("രണ്ടര randara", "mult", "2.5"),
    ("കാൽ kaal", "delta", "0.25"),
    ("മുക്കാൽ mukkaal", "delta", "-0.25"),
)

# ---------------------------------------------------------------------------
# Tamil
# ---------------------------------------------------------------------------

TA_NUMBERS = _numbers(
    (0, "பூஜ்யம் poojyam"),
    (1, "ஒன்று onru ஒரு oru"),
    (2, "இரண்டு irandu"),
    (3, "மூன்று moonru"),
    (4, "நான்கு naangu"),
    (5, "ஐந்து aindhu"),
    (6, "ஆறு aaru"),
    (7, "ஏழு eazhu"),
    (8, "எட்டு ettu"),
    (9, "ஒன்பது onbadhu"),
    (10, "பத்து pathu"),
    (11, "பதினொன்று pathinonru"),
    (12, "பன்னிரண்டு pannirandu பன்னிரெண்டு pannirendu"),
    (13, "பதிமூன்று pathimoonru"),
    (14, "பதினான்கு pathinaangu"),
    (15, "பதினைந்து pathinaindhu"),
    (16, "பதினாறு pathinaaru"),
    (17, "பதினேழு pathinezhu"),
    (18, "பதினெட்டு pathinettu"),
    (19, "பத்தொன்பது pathonbadhu"),
    (20, "இருபது irupathu"),
    (25, "இருபத்து ஐந்து irupathu aindhu"),
    (30, "முப்பது muppathu"),
    (40, "நாற்பது naarpathu"),
    (50, "ஐம்பது aimbathu"),
    (60, "அறுபது arupathu"),
    (70, "எழுபது ezhupathu"),
    (80, "எண்பது enpathu"),
    (90, "தொண்ணூறு thonnooru"),
    (100, "நூறு nooru நூற்று noottru நூற்றி noottri நூற்ற nootra"),
    (150, "நூற்றைம்பது noottaimbathu"),
    (200, "இருநூறு irunooru இருநூற்று irunoottru இருநூற்றி irunoottri"),
    (250, "இருநூற்றைம்பது irunoottaimbathu"),
    (1000, "ஆயிரம் aayiram ஆயிரத்து aayirathu"),
    (2000, "இரண்டாயிரம் irandaayiram இரண்டாயிரத்து irandaayirathu"),
    (3000, "மூன்றாயிரம் moonraayiram மூன்றாயிரத்து moonraayirathu"),
    (5000, "ஐயாயிரம் aiyaayiram ஐயாயிரத்து aiyaayirathu"),
    (6000, "ஆறாயிரம் aaraayiram ஆறாயிரத்து aaraayirathu"),
    (10000, "பத்தாயிரம் paththaayiram பத்தாயிரத்து paththaayirathu"),
    (12000, "பன்னிரண்டாயிரம் pannirandaayiram பன்னிரண்டாயிரத்து pannirandaayirathu"),
    (300, "முந்நூறு munnooru"),
    (400, "நானூறு naanooru"),
    (500, "ஐந்நூறு ainnooru ஐநூறு ainooru ஐநூற்று ainoottru"),
    (600, "அறுநூறு arunooru"),
    (700, "எழுநூறு ezhunooru"),
    (800, "எண்ணூறு ennooru"),
    (900, "தொள்ளாயிரம் thollayiram"),
)
TA_SCALES = _scales(
    (100, "நூற்று noottru"),
    (1000, "ஆயிரம் aayiram ஆயிரத்து aayirathu"),
    (100000, "லட்சம் latcham லட்ச latcha லட்சத்து latchathu"),
    (10000000, "கோடி kodi"),
)
TA_FRACTIONS = _fractions(
    ("ஒன்றரை onrarai", "mult", "1.5"),
    ("இரண்டரை irandarai", "mult", "2.5"),
    ("கால் kaal", "delta", "0.25"),
    ("முக்கால் mukkaal", "delta", "-0.25"),
)

# ---------------------------------------------------------------------------
# Telugu
# ---------------------------------------------------------------------------

TE_NUMBERS = _numbers(
    (0, "సున్నా sunna"),
    (1, "ఒకటి okati ఒక oka"),
    (2, "రెండు rendu"),
    (3, "మూడు moodu"),
    (4, "నాలుగు naalugu"),
    (5, "ఐదు aidu"),
    (6, "ఆరు aaru"),
    (7, "ఏడు edu"),
    (8, "ఎనిమిది enimidi"),
    (9, "తొమ్మిది tommidi"),
    (10, "పది padi"),
    (11, "పదకొండు padakondi"),
    (12, "పన్నెండు pannendu"),
    (13, "పదమూడు padamoodu"),
    (14, "పద్నాలుగు padnaalugu"),
    (15, "పదిహేను padihenu"),
    (16, "పదహారు padahaaru"),
    (17, "పదిహేడు padihedu"),
    (18, "పద్దెనిమిది paddenimidi"),
    (19, "పంతొమ్మిది pantommidi"),
    (20, "ఇరవై iravai"),
    (25, "ఇరవై ఐదు iravai aidu"),
    (30, "ముప్పై muppai"),
    (40, "నలభై nalabhai"),
    (50, "యాభై yaabhai"),
    (60, "అరవై aravai"),
    (70, "డెబ్బై debbai"),
    (80, "ఎనభై enabhai"),
    (90, "తొంభై tombhai"),
    (100, "వంద vanda నూరు nooru నూట noota"),
    (150, "నూట యాభై noota yaabhai"),
    (200, "రెండు వందల rendu vandala రెండు వందలు rendu vandalu"),
    (300, "మూడు వందల moodu vandala మూడు వందలు moodu vandalu"),
    (400, "నాలుగు వందల naalugu vandala నాలుగు వందలు naalugu vandalu"),
    (500, "ఐదు వందల aidu vandala ఐదు వందలు aidu vandalu"),
    (600, "ఆరు వందల aaru vandala ఆరు వందలు aaru vandalu"),
    (700, "ఏడు వందల edu vandala ఏడు వందలు edu vandalu"),
    (800, "ఎనిమిది వందల enimidi vandala ఎనిమిది వందలు enimidi vandalu"),
    (900, "తొమ్మిది వందల tommidi vandala తొమ్మిది వందలు tommidi vandalu"),
)
TE_SCALES = _scales(
    (100, "వందల vandala వందలు vandalu వంద vanda"),
    (1000, "వేయి veyi వెయ్యి veyyi వేల vela వేలు velu"),
    (100000, "లక్ష lakhsa లక్షల lakhsala"),
    (10000000, "కోటి koti"),
)
TE_FRACTIONS = _fractions(
    ("ఒకటిన్నర okatinnara", "mult", "1.5"),
    ("రెండున్నర rendunnara", "mult", "2.5"),
    ("పావు paavu", "delta", "0.25"),
    ("ముప్పావు muppaavu", "delta", "-0.25"),
)

# ---------------------------------------------------------------------------
# Vocabulary bundle per language code prefix
# ---------------------------------------------------------------------------


class LangWords:
    """Number vocabulary plus the verbs that are not part of a name."""

    __slots__ = ("numbers", "scales", "fractions", "verbs", "intents", "postpositions")

    def __init__(self, numbers, scales, fractions, verbs, intents, postpositions):
        self.numbers = numbers
        self.scales = scales
        self.fractions = fractions
        self.verbs = verbs
        self.intents = intents
        self.postpositions = postpositions


# Verbs are removed before name extraction, never used to guess an amount.
# `intents` holds the udhaar / jama / balance words for that language; a word in
# `verbs` alone does not decide intent.
LANGUAGES: dict[str, LangWords] = {
    "mr": LangWords(
        MR_NUMBERS,
        MR_SCALES,
        MR_FRACTIONS,
        frozenset(
            "लिही लिख लिहा लिहून दिले दिला देणे दिली घेतले घेतला परत मिळाले मिळाला जमा बाकी किती करा कर".split()
        ),
        {
            "credit": ("उधार", "उधारी", "udhar", "udhaar"),
            "payment": ("जमा", "परत", "jama", "परत दिले"),
            "balance": ("किती बाकी", "बाकी किती", "किती उधार", "बाकी"),
        },
        ("ला", "ने", "चा", "ची", "चे"),
    ),
    "gu": LangWords(
        GU_NUMBERS,
        GU_SCALES,
        GU_FRACTIONS,
        frozenset(
            "લખ લખો લખી લખવું આપ્યા આપ્યું આપો દીધા દીધું દો મળ્યા મળ્યું જમા પરત કરો કરવું".split()
        ),
        {
            "credit": ("ઉધાર", "udhar", "udhaar"),
            "payment": ("જમા", "પરત", "jama"),
            "balance": ("કેટલું બાકી", "કેટલી બાકી", "બાકી કેટલું", "બાકી"),
        },
        ("ને", "નો", "ની", "નું"),
    ),
    "pa": LangWords(
        PA_NUMBERS,
        PA_SCALES,
        PA_FRACTIONS,
        frozenset(
            "ਲਿਖ ਲਿਖੋ ਲਿਖੀ ਦਿੱਤੇ ਦਿੱਤਾ ਦੇ ਦੇਣਾ ਦਿਓ ਮਿਲੇ ਮਿਲਿਆ ਜਮ੍ਹਾ ਜਮਾ ਵਾਪਸ ਪਰਤ ਕਰੋ".split()
        ),
        {
            "credit": ("ਉਧਾਰ", "udhar", "udhaar"),
            "payment": ("ਜਮ੍ਹਾ", "ਜਮਾ", "ਵਾਪਸ", "jama"),
            "balance": ("ਕਿੰਨਾ ਬਾਕੀ", "ਕਿੰਨੀ ਬਾਕੀ", "ਬਾਕੀ"),
        },
        ("ਨੂੰ", "ਦਾ", "ਦੀ", "ਦੇ"),
    ),
    "bn": LangWords(
        BN_NUMBERS,
        BN_SCALES,
        BN_FRACTIONS,
        frozenset(
            "লেখো লিখো লেখ লিখ লিখুন দিল দিলাম দিয়েছি দিয়েছে দে দাও পেলাম পেয়েছি জমা ফেরত করো কর".split()
        ),
        {
            "credit": ("ধার", "udhar", "udhaar"),
            "payment": ("জমা", "ফেরত", "পরিশোধ", "jama"),
            "balance": ("কত বাকি", "বাকি কত", "বাকি"),
        },
        ("কে", "এর", "র"),
    ),
    "kn": LangWords(
        KN_NUMBERS,
        KN_SCALES,
        KN_FRACTIONS,
        frozenset(
            "ಬರೆ ಬರೆಯಿರಿ ಬರೆಯಬೇಕು ಬರೆದು ಕೊಟ್ಟೆ ಕೊಟ್ಟರು ಕೊಡು ಕೊಡಿ ಬಂತು ಪಡೆದೆ ಜಮಾ ಹಿಂತಿರುಗಿ ವಾಪಸ್ ಮಾಡಿ".split()
        ),
        {
            "credit": ("ಸಾಲ", "udhar", "udhaar"),
            "payment": ("ಜಮಾ", "ಪಾವತಿ", "ಹಿಂತಿರುಗಿ", "jama"),
            "balance": ("ಎಷ್ಟು ಬಾಕಿ", "ಬಾಕಿ"),
        },
        ("ಗೆ", "ಇಗೆ"),
    ),
    "ml": LangWords(
        ML_NUMBERS,
        ML_SCALES,
        ML_FRACTIONS,
        frozenset(
            "എഴുതൂ എഴുതുക എഴുതി എഴുതണം കൊടുത്തു തന്നു കൊടുക്കൂ കിട്ടി ലഭിച്ചു ജമ തിരികെ ചെയ്യൂ".split()
        ),
        {
            # Prisma writes "കടം എഴുതൂ" glued as "കടമെഴുതൂ", so the bare stem
            # is listed too; "അടച്ചു" is how a shop says "paid".
            "credit": ("കടം", "കടമ", "udhar", "udhaar"),
            "payment": ("ജമ", "തിരികെ", "അടച്ചു", "നൽകി", "jama"),
            "balance": ("എത്ര ബാക്കി", "ബാക്കി"),
        },
        ("ന്", "ന്റെ", "നു"),
    ),
    "ta": LangWords(
        TA_NUMBERS,
        TA_SCALES,
        TA_FRACTIONS,
        frozenset(
            "எழுது எழுதுங்க எழுதவும் எழுதியது கொடுத்தார் கொடு தந்தார் கிடைத்தது வந்தது செலுத்தினார் திரும்ப செய்".split()
        ),
        {
            "credit": ("கடன்", "udhar", "udhaar"),
            "payment": ("செலுத்த", "திரும்ப", "கிடைத்தது", "jama"),
            "balance": ("எவ்வளவு", "பாக்கி", "மீதம்"),
        },
        ("க்கு", "ஐ", "இன்"),
    ),
    "te": LangWords(
        TE_NUMBERS,
        TE_SCALES,
        TE_FRACTIONS,
        frozenset(
            "రాయి రాయండి రాసి రాయాలి ఇచ్చారు ఇవ్వు ఇచ్చాను వచ్చింది జమ తిరిగి చేయి".split()
        ),
        {
            "credit": ("అప్పు", "udhar", "udhaar"),
            "payment": ("జమ", "తిరిగి", "చెల్లించారు", "jama"),
            "balance": ("ఎంత", "బాకీ", "మిగిలింది"),
        },
        ("కి", "కు"),
    ),
}


def words_for(base: str) -> LangWords | None:
    return LANGUAGES.get(base)


def all_languages() -> tuple[str, ...]:
    return tuple(LANGUAGES)
