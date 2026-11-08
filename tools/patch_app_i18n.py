"""Splice the unified language module into static/app.js.

Steps: drop the three embedded dictionaries, replace the old
voice-language + UI-language code with tools/language_block.js, remove the
`#ui-lang` dropdown handlers, route the hardcoded toasts/busy text through t(),
and make boot await the single async language init.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "static" / "app.js"
BLOCK = pathlib.Path(__file__).with_name("language_block.js")

src = APP.read_bytes().decode("utf-8")
newline = "\r\n" if "\r\n" in src else "\n"
src = src.replace("\r\n", "\n")

SECTIONS = "/* ------------------------------------------------------------------ */\n/* Sections: Bolo / Grahak / Hisaab"

# 1) embedded dictionaries -> data files
start = src.index("const I18N = {")
dict_end = (
    "Object.entries(EXTRA_I18N).forEach(([lang, dict]) => {\n"
    "  if (I18N[lang]) Object.assign(I18N[lang], dict);\n"
    "});"
)
end = src.index(dict_end) + len(dict_end)
src = src[:start] + "/* Interface strings live in /static/i18n/<lang>.json; see i18n.js. */" + src[end:]

# 2) voice-language + UI-language code -> one module
start = src.index('let UI_LANG = "hing";')
end = src.index(SECTIONS)
src = src[:start] + BLOCK.read_text(encoding="utf-8").rstrip() + "\n\n" + src[end:]

# 3) the removed setting's constant
src = src.replace('const UI_LANG_KEY = "vk-ui-lang";\n\n', "")

# 4) boot: one async init instead of two
src = src.replace(
    "  initLanguage();\n  bindEvents();\n  initVoiceLanguage();",
    "  bindEvents();\n  await initLanguage();",
)

# 5) header toggle + modal cards use the unified setter
src = src.replace(
    '      const button = event.target.closest("[data-voice-lang]");\n'
    "      if (button) chooseLanguage(button.dataset.voiceLang);",
    '      const button = event.target.closest("[data-voice-lang]");\n'
    "      if (!button) return;\n"
    '      if (button.dataset.voiceLang === "en-IN") setLanguage("en-IN");\n'
    "      else openLanguageModal();",
)
src = src.replace(
    "      const card = event.target.closest(\"[data-lang]\");\n"
    "      if (card) {\n"
    "        chooseLanguage(card.dataset.lang);",
    "      const card = event.target.closest(\"[data-lang]\");\n"
    "      if (card) {\n"
    '        chooseLanguage(card.dataset.lang, card.dataset.script === "latn");',
)

# 6) the removed dropdown listener
old_dropdown = (
    '  $("#ui-lang").addEventListener("change", (event) => {\n'
    "    const lang = event.target.value;\n"
    "    UI_LANG_EXPLICIT = lang;\n"
    "    applyLanguage(lang);\n"
    '    try { localStorage.setItem(UI_LANG_KEY, lang); } catch { /* storage blocked */ }\n'
    "  });\n\n"
)
if old_dropdown in src:
    src = src.replace(old_dropdown, "")
else:
    print("WARN: dropdown listener not found verbatim", file=sys.stderr)

# 7) hardcoded toasts and busy text
plain = {
    'toast("Pehle command likhein ya bolein.", "warn")': 'toast(t("toast_need_command"), "warn")',
    'toast("Pehle command bolein ya likhein.", "warn")': 'toast(t("toast_need_command"), "warn")',
    'toast("Kuch likhein ya bolein.", "warn")': 'toast(t("toast_need_command"), "warn")',
    'toast("Recording play nahi ho saki.", "warn")': 'toast(t("toast_play_failed"), "warn")',
    'toast("Hisaab refresh ho gaya.", "success", 2400)': 'toast(t("toast_refresh_done"), "success", 2400)',
    'toast("Voice aur audio status refresh hua.", "success", 2400)': 'toast(t("toast_status_refreshed"), "success", 2400)',
    'toast("Text mein command likh kar Bhejein dabaiye.", "info")': 'toast(t("toast_text_hint"), "info")',
    'toast("Payment baaki se zyada hai. Confirm dobara dabaiye to advance jama hoga.", "warn", 5000)': 'toast(t("toast_overpay_ack"), "warn", 5000)',
    'showBusy("Samajh rahe hain…", "Customer, amount aur kaam check ho raha hai")': 'showBusy(t("busy_understanding"), t("busy_understanding_sub"))',
    'showBusy("Hisaab save ho raha hai…", "Database commit ke baad hi jawab milega")': 'showBusy(t("busy_saving"), t("busy_saving_sub"))',
    'showBusy("Cancel kar rahe hain…", "Ledger nahi badlega")': 'showBusy(t("busy_cancelling"), t("busy_cancelling_sub"))',
    'showBusy("Sun rahe hain…", "Gnani Prisma se transcript aa raha hai")': 'showBusy(t("busy_listening"), t("busy_transcribing"))',
    'toast("Transaction cancel — ledger nahi badla.", "success", 3200)': 'toast(t("toast_cancel_done"), "success", 3200)',
    'toast(\n    "Transcript theek karein aur Bhejein dabaiye. Naya preview banega — tab tak kuch save nahi hota.",\n    "info",\n    4500\n  )': 'toast(t("toast_edit_transcript"), "info", 4500)',
    'toast("Naam kam se kam 2 letters ka likhein.", "warn")': 'toast(t("toast_name_short"), "warn")',
    'toast(`${result.customer.name} ledger mein add ho gaye.`, "success", 3000)': 'toast(t("toast_customer_added", { name: result.customer.name }), "success", 3000)',
    'toast("Pehle customer chunein. Zarurat ho to pehle customer add karein.", "warn")': 'toast(t("toast_pick_customer"), "warn")',
    'toast("Amount zero se bada hona chahiye.", "warn")': 'toast(t("toast_amount_positive"), "warn")',
    'showBusy("Preview ban raha hai…", "Koi transaction abhi save nahi hua")': 'showBusy(t("busy_preview"), t("busy_preview_sub"))',
}
for old, new in plain.items():
    if old not in src:
        print(f"WARN: not found: {old[:60]}", file=sys.stderr)
    src = src.replace(old, new)

# 7b) intent labels + transcript chips through t()
src = src.replace(
    'const INTENT_LABELS = {\n  add_credit: "Udhaar likhna",\n  record_payment: "Payment jama",\n  balance_query: "Balance sawal",\n  top_debtor: "Sabse zyada udhaar",\n  daily_summary: "Aaj ka hisaab",\n  unknown: "Samajh nahi aaya",\n};',
    'const INTENT_KEYS = {\n  add_credit: "intent_credit",\n  record_payment: "intent_payment",\n  balance_query: "intent_balance",\n  top_debtor: "intent_top",\n  daily_summary: "intent_daily",\n};\n\nfunction intentLabel(intent) {\n  return t(INTENT_KEYS[intent] || "cmd_label");\n}',
)
src = src.replace(
    '${escapeHtml(INTENT_LABELS[parser.intent] || parser.intent)}',
    '${escapeHtml(intentLabel(parser.intent))}',
)
src = src.replace(
    '${source === "voice" ? "Awaaz se" : "Text se"}',
    '${escapeHtml(source === "voice" ? t("meta_voice") : t("meta_text"))}',
)
src = src.replace('<b>Kaam:</b> ', '<b>${escapeHtml(t("meta_action"))}:</b> ')
src = src.replace('<b>Amount:</b> ', '<b>${escapeHtml(t("meta_amount"))}:</b> ')
src = src.replace('<b>Customer:</b> ', '<b>${escapeHtml(t("row_customer"))}:</b> ')

# 8) keep language state on the app state object
if "hinglish: false," not in src:
    src = src.replace(
        "const state = {",
        "const state = {\n  hinglish: false, // Hinglish = hi-IN voice, Roman interface",
        1,
    )

APP.write_bytes(src.replace("\n", newline).encode("utf-8"))
print("app.js patched:", len(src.splitlines()), "lines")
