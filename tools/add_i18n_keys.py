"""Add the keys introduced by the language-unification work to the existing
dictionaries (en, hi, hing, mr) so no file is left with stale translations."""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
I18N = ROOT / "static" / "i18n"

NEW: dict[str, dict[str, str]] = {
    "app_title": {
        "en": "HisabSetu AI — your ledger, your language",
        "hi": "हिसाबसेतु AI — हिसाब, आपकी भाषा में",
        "hing": "HisabSetu AI — hisaab, aapki bhasha mein",
        "mr": "हिशोबसेतू AI — हिशोब, तुमच्या भाषेत",
    },
    "hinglish_card": {
        "en": "Hinglish (Roman)",
        "hi": "Hinglish (रोमन)",
        "hing": "Hinglish (Roman)",
        "mr": "Hinglish (रोमन)",
    },
    "net_word": {"en": "Net", "hi": "बदलाव", "hing": "Net", "mr": "बदल"},
    "entries_word": {"en": "entries", "hi": "एंट्री", "hing": "entry", "mr": "नोंदी"},
    "customers_word": {"en": "customers", "hi": "ग्राहक", "hing": "customer", "mr": "ग्राहक"},
    "aria_change_language": {
        "en": "Change language", "hi": "भाषा बदलें", "hing": "Bhasha badlein", "mr": "भाषा बदला",
    },
    "aria_lang_group": {
        "en": "Speaking and interface language",
        "hi": "बोलने और दिखाने की भाषा",
        "hing": "Bolne aur dikhane ki bhasha",
        "mr": "बोलण्याची आणि दाखवण्याची भाषा",
    },
    "aria_theme": {
        "en": "Dark or light mode", "hi": "डार्क या लाइट मोड",
        "hing": "Dark ya light mode", "mr": "डार्क किंवा लाइट मोड",
    },
    "aria_refresh": {
        "en": "Refresh data", "hi": "डेटा रीफ़्रेश करें",
        "hing": "Data refresh karein", "mr": "डेटा रिफ्रेश करा",
    },
    "aria_mic": {
        "en": "Tap to speak", "hi": "बोलने के लिए दबाएँ",
        "hing": "Bolne ke liye dabaiye", "mr": "बोलण्यासाठी दाबा",
    },
    "aria_add_customer": {
        "en": "Add a customer", "hi": "नया ग्राहक जोड़ें",
        "hing": "Naya customer banayein", "mr": "नवीन ग्राहक जोडा",
    },
    "aria_status_refresh": {
        "en": "Refresh status", "hi": "स्थिति रीफ़्रेश करें",
        "hing": "Status refresh karein", "mr": "स्थिती रिफ्रेश करा",
    },
    "aria_speak_summary": {
        "en": "Read today's summary aloud", "hi": "आज का हिसाब सुनाएँ",
        "hing": "Aaj ka hisaab sunao", "mr": "आजचा हिशोब ऐकवा",
    },
    "aria_customer_search": {
        "en": "Search customers", "hi": "ग्राहक खोजें",
        "hing": "Customer dhoondein", "mr": "ग्राहक शोधा",
    },
    "aria_nav": {
        "en": "App sections", "hi": "ऐप के सेक्शन",
        "hing": "App ke section", "mr": "ॲपचे विभाग",
    },
    "aria_examples": {
        "en": "Example commands", "hi": "उदाहरण कमांड",
        "hing": "Example commands", "mr": "उदाहरण कमांड",
    },
    "aria_ask_customer": {
        "en": "Ask for {name}'s balance", "hi": "{name} का बैलेंस पूछें",
        "hing": "{name} ka balance poochhein", "mr": "{name} यांचा हिशोब विचारा",
    },
    "aria_new_customer_name": {
        "en": "New customer name", "hi": "नए ग्राहक का नाम",
        "hing": "Naya customer ka naam", "mr": "नवीन ग्राहकाचे नाव",
    },
    "aria_transcript": {
        "en": "What you said", "hi": "आपने क्या कहा",
        "hing": "Aapne kya kaha", "mr": "तुम्ही काय म्हणालात",
    },
    "toast_language_set": {
        "en": "{name} selected — speak in this language now.",
        "hi": "{name} चुनी गई — अब इस भाषा में बोलें।",
        "hing": "{name} chuni gayi — ab is bhasha mein bolein.",
        "mr": "{name} निवडली — आता या भाषेत बोला.",
    },
    "toast_need_command": {
        "en": "Say or type a command first.", "hi": "पहले कमांड बोलें या लिखें।",
        "hing": "Pehle command likhein ya bolein.", "mr": "आधी कमांड बोला किंवा लिहा.",
    },
    "toast_play_failed": {
        "en": "That recording could not be played.", "hi": "यह रिकॉर्डिंग चल नहीं सकी।",
        "hing": "Recording play nahi ho saki.", "mr": "रेकॉर्डिंग वाजू शकली नाही.",
    },
    "toast_refresh_done": {
        "en": "Ledger refreshed.", "hi": "हिसाब रीफ़्रेश हो गया।",
        "hing": "Hisaab refresh ho gaya.", "mr": "हिशोब रिफ्रेश झाला.",
    },
    "toast_status_refreshed": {
        "en": "Voice and audio status refreshed.", "hi": "आवाज़ और ऑडियो स्थिति रीफ़्रेश हुई।",
        "hing": "Voice aur audio status refresh hua.", "mr": "आवाज आणि ऑडिओ स्थिती रिफ्रेश झाली.",
    },
    "toast_text_hint": {
        "en": "Type the command and press Send.", "hi": "कमांड लिखें और भेजें दबाएँ।",
        "hing": "Text mein command likh kar Bhejein dabaiye.", "mr": "टेक्स्टमध्ये कमांड लिहा आणि पाठवा दाबा.",
    },
    "toast_overpay_ack": {
        "en": "This payment is more than the balance. Press confirm again to record it as advance.",
        "hi": "यह भुगतान बाकी से ज़्यादा है। अग्रिम में लिखने के लिए दोबारा पक्का करें।",
        "hing": "Payment baaki se zyada hai. Confirm dobara dabaiye to advance jama hoga.",
        "mr": "जमा बाकीपेक्षा जास्त आहे. अग्रिम म्हणून नोंदवण्यासाठी पुन्हा निश्चित करा.",
    },
    "busy_understanding": {
        "en": "Understanding…", "hi": "समझ रहे हैं…",
        "hing": "Samajh rahe hain…", "mr": "समजून घेत आहोत…",
    },
    "busy_understanding_sub": {
        "en": "Checking customer, amount and action", "hi": "ग्राहक, रकम और काम जाँच रहे हैं",
        "hing": "Customer, amount aur kaam check ho raha hai", "mr": "ग्राहक, रक्कम आणि काम तपासत आहोत",
    },
    "busy_saving": {
        "en": "Saving to the ledger…", "hi": "हिसाब में सेव हो रहा है…",
        "hing": "Hisaab save ho raha hai…", "mr": "हिशोबात सेव्ह होत आहे…",
    },
    "busy_saving_sub": {
        "en": "The reply comes only after the database commit", "hi": "डेटाबेस में सेव होने के बाद ही जवाब आएगा",
        "hing": "Database commit ke baad hi jawab milega", "mr": "डेटाबेसमध्ये सेव्ह झाल्यावरच उत्तर येईल",
    },
    "busy_cancelling": {
        "en": "Cancelling…", "hi": "रद्द कर रहे हैं…",
        "hing": "Cancel kar rahe hain…", "mr": "रद्द करत आहोत…",
    },
    "busy_cancelling_sub": {
        "en": "The ledger will not change", "hi": "हिसाब नहीं बदलेगा",
        "hing": "Ledger nahi badlega", "mr": "हिशोब बदलणार नाही",
    },
    "busy_listening": {
        "en": "Listening…", "hi": "सुन रहे हैं…", "hing": "Sun rahe hain…", "mr": "ऐकत आहोत…",
    },
    "toast_edit_transcript": {
        "en": "Fix the transcript and press Send. It builds a new preview — nothing is saved until you confirm.",
        "hi": "ट्रांसक्रिप्ट सुधारें और भेजें दबाएँ। नया प्रीव्यू बनेगा — पक्का करने तक कुछ सेव नहीं होता।",
        "hing": "Transcript theek karein aur Bhejein dabaiye. Naya preview banega — tab tak kuch save nahi hota.",
        "mr": "ट्रान्स्क्रिप्ट दुरुस्त करा आणि पाठवा दाबा. नवीन झलक तयार होईल — निश्चित करेपर्यंत काहीही सेव्ह होत नाही.",
    },
    "meta_voice": {"en": "By voice", "hi": "आवाज़ से", "hing": "Awaaz se", "mr": "आवाजातून"},
    "meta_text": {"en": "By text", "hi": "टेक्स्ट से", "hing": "Text se", "mr": "टेक्स्टने"},
    "meta_action": {"en": "Action", "hi": "काम", "hing": "Kaam", "mr": "काम"},
    "meta_amount": {"en": "Amount", "hi": "रकम", "hing": "Amount", "mr": "रक्कम"},
    "intent_credit": {
        "en": "Record credit", "hi": "उधार लिखना", "hing": "Udhaar likhna", "mr": "उधार लिहिणे",
    },
    "intent_payment": {
        "en": "Record payment", "hi": "भुगतान लेना", "hing": "Payment lena", "mr": "जमा घेणे",
    },
    "intent_balance": {
        "en": "Check balance", "hi": "बैलेंस पूछना", "hing": "Balance poochna", "mr": "हिशोब विचारणे",
    },
    "intent_top": {
        "en": "Highest due", "hi": "सबसे ज़्यादा उधार", "hing": "Sabse zyada udhaar", "mr": "सर्वाधिक उधार",
    },
    "intent_daily": {
        "en": "Today's summary", "hi": "आज का हिसाब", "hing": "Aaj ka hisaab", "mr": "आजचा हिशोब",
    },
    "toast_cancel_done": {
        "en": "Transaction cancelled — the ledger did not change.",
        "hi": "लेन-देन रद्द — हिसाब नहीं बदला।",
        "hing": "Transaction cancel — ledger nahi badla.",
        "mr": "व्यवहार रद्द — हिशोब बदलला नाही.",
    },
    "toast_name_short": {
        "en": "Use at least 2 letters for the name.",
        "hi": "नाम कम से कम 2 अक्षरों का लिखें।",
        "hing": "Naam kam se kam 2 letters ka likhein.",
        "mr": "नाव कमीत कमी २ अक्षरांचे लिहा.",
    },
    "toast_customer_added": {
        "en": "{name} added to the ledger.",
        "hi": "{name} हिसाब में जुड़ गए।",
        "hing": "{name} ledger mein add ho gaye.",
        "mr": "{name} हिशोबात जोडले गेले.",
    },
    "toast_pick_customer": {
        "en": "Choose a customer first. Add one if you need to.",
        "hi": "पहले ग्राहक चुनें। ज़रूरत हो तो पहले ग्राहक जोड़ें।",
        "hing": "Pehle customer chunein. Zarurat ho to pehle customer add karein.",
        "mr": "आधी ग्राहक निवडा. गरज असेल तर आधी ग्राहक जोडा.",
    },
    "toast_amount_positive": {
        "en": "The amount must be more than zero.",
        "hi": "रकम शून्य से बड़ी होनी चाहिए।",
        "hing": "Amount zero se bada hona chahiye.",
        "mr": "रक्कम शून्यापेक्षा जास्त असावी.",
    },
    "busy_preview": {
        "en": "Building the preview…", "hi": "प्रीव्यू बन रहा है…",
        "hing": "Preview ban raha hai…", "mr": "झलक तयार होत आहे…",
    },
    "busy_preview_sub": {
        "en": "Nothing is saved yet", "hi": "अभी कुछ भी सेव नहीं हुआ",
        "hing": "Koi transaction abhi save nahi hua", "mr": "अजून काहीही सेव्ह झाले नाही",
    },
    "busy_transcribing": {
        "en": "Getting the transcript from Gnani Prisma",
        "hi": "Gnani Prisma से ट्रांसक्रिप्ट आ रहा है",
        "hing": "Gnani Prisma se transcript aa raha hai",
        "mr": "Gnani Prisma कडून ट्रान्स्क्रिप्ट येत आहे",
    },
}


def main() -> int:
    for lang in ("en", "hi", "hing", "mr"):
        path = I18N / f"{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, values in NEW.items():
            data[key] = values[lang]
        ordered = {key: data[key] for key in sorted(data)}
        path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(lang, len(ordered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
