"""Thread the active language through services.py and localise its replies."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / "services.py"
src = P.read_bytes().decode("utf-8")
newline = "\r\n" if "\r\n" in src else "\n"
src = src.replace("\r\n", "\n")

HI = 'str(language or "hi-IN").lower().startswith("hi")'


def sub(old: str, new: str, label: str) -> None:
    global src
    if old not in src:
        print(f"MISS: {label}", file=sys.stderr)
        return
    src = src.replace(old, new, 1)


# 1) import
if "from messages import tr" not in src:
    src = src.replace("class ServiceError", "from messages import tr\n\n\nclass ServiceError", 1)

# 2) serialize_transaction
sub(
    "def serialize_transaction(txn: Transaction, customer: Customer | None = None) -> dict:",
    "def serialize_transaction(\n    txn: Transaction, customer: Customer | None = None, language: str = \"hi-IN\"\n) -> dict:",
    "serialize signature",
)
sub(
    '        "type_label": "Udhaar diya" if txn.type == TYPE_CREDIT else "Payment mila",',
    '        "type_label": (\n            tr(language, "type_credit") if txn.type == TYPE_CREDIT else tr(language, "type_payment")\n        ),',
    "serialize type_label",
)

# 3) amount validation
sub(
    "def _validate_amount_paise(amount_rupees: Decimal | None) -> int:",
    'def _validate_amount_paise(amount_rupees: Decimal | None, language: str = "hi-IN") -> int:',
    "validate signature",
)
sub(
    '        raise ServiceError("missing_amount", "Amount nahi mila. Kitne rupaye ka udhaar hai?", 422)',
    '        raise ServiceError("missing_amount", tr(language, "err_amount_missing"), 422)',
    "missing amount",
)
sub(
    '        raise ServiceError("invalid_amount", "Amount sahi number nahi hai.", 422)',
    '        raise ServiceError("invalid_amount", tr(language, "err_amount_invalid"), 422)',
    "invalid amount",
)
sub(
    '            f"Amount ₹{settings.max_amount_rupees:,} se zyada nahi ho sakta.",',
    '            tr(language, "err_amount_too_large", limit=f"₹{settings.max_amount_rupees:,}"),',
    "too large",
)
src = src.replace(
    '"Amount zero se bada hona chahiye."', 'tr(language, "err_amount_positive")'
)

# 4) create_pending signature + preview text
sub(
    "    source: str,\n    parser_info: dict,\n) -> dict:",
    '    source: str,\n    parser_info: dict,\n    language: str = "hi-IN",\n) -> dict:',
    "create_pending signature",
)
sub(
    '        raise ServiceError("invalid_type", "Transaction type sahi nahi hai.", 422)',
    '        raise ServiceError("invalid_type", tr(language, "err_invalid_type"), 422)',
    "pending invalid type",
)
sub(
    """    is_credit = txn_type == TYPE_CREDIT
    action = "udhaar" if is_credit else "jama"
    message = (
        f"{customer.name} ji ka {format_inr(amount_paise)} {action} likhna hai? "
        "Confirm karein ya cancel karein."
    )
    if is_credit:
        speech = (
            f"{customer.name} जी का {hindi_rupee_words(amount_paise)} का उधार लिखना है। "
            f"अभी बकाया {hindi_rupee_words(balance_before)} है, इसके बाद "
            f"{hindi_rupee_words(balance_after)} हो जाएगा।"
        )
    else:
        speech = (
            f"{customer.name} जी से {hindi_rupee_words(amount_paise)} जमा करने हैं। "
            f"अभी बकाया {hindi_rupee_words(balance_before)} है, इसके बाद "
            f"{hindi_rupee_words(balance_after)} रहेगा।"
        )
    if requires_ack:
        message += " Dhyan dein: payment baaki raqam se zyada hai, advance jama hoga."
        speech += " ध्यान दें, यह रकम बकाया से ज़्यादा है, इसलिए एडवांस जमा होगा。"
""".replace("。", "।"),
    f"""    is_credit = txn_type == TYPE_CREDIT
    message = tr(
        language,
        "preview_credit_msg" if is_credit else "preview_payment_msg",
        name=customer.name,
        amount=format_inr(amount_paise),
    )
    if {HI}:
        if is_credit:
            speech = (
                f"{{customer.name}} जी का {{hindi_rupee_words(amount_paise)}} का उधार लिखना है। "
                f"अभी बकाया {{hindi_rupee_words(balance_before)}} है, इसके बाद "
                f"{{hindi_rupee_words(balance_after)}} हो जाएगा।"
            )
        else:
            speech = (
                f"{{customer.name}} जी से {{hindi_rupee_words(amount_paise)}} जमा करने हैं। "
                f"अभी बकाया {{hindi_rupee_words(balance_before)}} है, इसके बाद "
                f"{{hindi_rupee_words(balance_after)}} रहेगा।"
            )
        if requires_ack:
            speech += " ध्यान दें, यह रकम बकाया से ज़्यादा है, इसलिए एडवांस जमा होगा।"
    else:
        speech = tr(
            language,
            "preview_credit_speech" if is_credit else "preview_payment_speech",
            name=customer.name,
            amount=format_inr(amount_paise),
            balance=format_inr(balance_before),
            after=format_inr(balance_after),
        )
        if requires_ack:
            speech += tr(language, "overpay_extra_speech")
    if requires_ack:
        message += tr(language, "overpay_extra_msg")
""",
    "create_pending message",
)
sub(
    '        "type_label": "Udhaar (credit)" if is_credit else "Payment (jama)",',
    '        "type_label": (\n            tr(language, "type_credit_pending")\n            if is_credit\n            else tr(language, "type_payment_pending")\n        ),',
    "pending type_label",
)

# 5) _transaction_proposal
sub(
    "    source: str,\n    customer_id: int | None,\n) -> dict:\n    amount_paise = _validate_amount_paise(parsed.amount_rupees)",
    '    source: str,\n    customer_id: int | None,\n    language: str = "hi-IN",\n) -> dict:\n    amount_paise = _validate_amount_paise(parsed.amount_rupees, language)',
    "proposal signature",
)
sub(
    '            "ambiguous_amount",\n            "Ek se zyada amount mile. Sahi amount likh kar bhejein.",',
    '            "ambiguous_amount",\n            tr(language, "clarify_multi_amount"),',
    "proposal ambiguous",
)
sub(
    "    proposal = create_pending(\n        db, customer, txn_type, amount_paise, transcript, source, _parser_payload(parsed)\n    )",
    "    proposal = create_pending(\n        db,\n        customer,\n        txn_type,\n        amount_paise,\n        transcript,\n        source,\n        _parser_payload(parsed),\n        language,\n    )",
    "proposal create_pending",
)
sub(
    """        proposal["message"] += (
            ' Dhyan dein: transcript mein "de do sau" tha, ise "dedh sau" maana gaya.'
            ' Galat ho toh "Sahi karein" dabayein.'
        )""",
    '        proposal["message"] += tr(language, "dedh_msg")',
    "dedh warning",
)

# 6) balance answer
sub(
    "def _balance_answer(db: Session, parsed: ParsedCommand, transcript: str, customer_id: int | None) -> dict:",
    'def _balance_answer(\n    db: Session,\n    parsed: ParsedCommand,\n    transcript: str,\n    customer_id: int | None,\n    language: str = "hi-IN",\n) -> dict:',
    "balance signature",
)
sub(
    '            question = "Kis customer ka balance dekhna hai?"\n            speech = "किस ग्राहक का बकाया देखना है?"',
    '            question = tr(language, "clarify_ask_customer")\n            speech = question if not {hi} else "किस ग्राहक का बकाया देखना है?"'.format(hi=HI),
    "balance ask",
)
sub(
    '            question = "Kaunsa customer? Ek naam chunein."\n            speech = "कौन से ग्राहक का बकाया? नीचे से नाम चुनें।"',
    '            question = tr(language, "clarify_ambiguous")\n            speech = question if not {hi} else "कौन से ग्राहक का बकाया? नीचे से नाम चुनें।"'.format(hi=HI),
    "balance ambiguous",
)
sub(
    """            question = f'"{parsed.customer_name}" naam ka customer nahi mila. Sahi customer chunein.'
            speech = "यह नाम का ग्राहक नहीं मिला। सही ग्राहक चुनें。"""".replace("。", "।"),
    f"""            question = tr(language, "clarify_no_match", name=parsed.customer_name)
            speech = question if not {HI} else "यह नाम का ग्राहक नहीं मिला। सही ग्राहक चुनें।"""",
    "balance no match",
)
sub(
    """    message = f"{customer.name} ji ka {phrase}."
    speech = f"{customer.name} जी का {speech_phrase}。"""".replace("。", "।"),
    f"""    if {HI}:
        message = f"{{customer.name}} ji ka {{phrase}}."
        speech = f"{{customer.name}} जी का {{speech_phrase}}।"
    else:
        message = tr(language, "balance_message", name=customer.name, phrase=phrase)
        speech = message""",
    "balance message",
)

# 7) top debtor
sub(
    "def _top_debtor_answer(db: Session, parsed: ParsedCommand, transcript: str) -> dict:",
    'def _top_debtor_answer(\n    db: Session, parsed: ParsedCommand, transcript: str, language: str = "hi-IN"\n) -> dict:',
    "top signature",
)
sub(
    """        message = "Abhi kisi customer ka udhaar baaki nahi hai."
        speech = "अभी किसी ग्राहक का उधार बाकी नहीं है。"""".replace("。", "।"),
    f"""        message = tr(language, "top_empty")
        speech = message if not {HI} else "अभी किसी ग्राहक का उधार बाकी नहीं है।"""",
    "top empty",
)
sub(
    """        message = f"Sabse zyada udhaar {first['name']} ji ka {first['balance_text']} hai."
        speech = (
            f"सबसे ज़्यादा उधार {first['name']} जी का "
            f"{hindi_rupee_words(first['balance_paise'])} है。"
        )""".replace("。", "।"),
    f"""        message = tr(
            language, "top_debtor", name=first["name"], amount=first["balance_text"]
        )
        if {HI}:
            speech = (
                f"सबसे ज़्यादा उधार {{first['name']}} जी का "
                f"{{hindi_rupee_words(first['balance_paise'])}} है।"
            )
        else:
            speech = message""",
    "top debtor",
)

# 8) daily answer
sub(
    "def _daily_answer(db: Session, parsed: ParsedCommand, transcript: str, day: date | None = None) -> dict:\n    summary = daily_summary(db, day)",
    'def _daily_answer(\n    db: Session,\n    parsed: ParsedCommand,\n    transcript: str,\n    day: date | None = None,\n    language: str = "hi-IN",\n) -> dict:\n    summary = daily_summary(db, day, language)',
    "daily answer",
)

# 9) handle_command plumbing
sub(
    "        return _transaction_proposal(db, parsed, transcript, source, customer_id)",
    "        return _transaction_proposal(db, parsed, transcript, source, customer_id, language)",
    "handle proposal",
)
sub(
    "        return _balance_answer(db, parsed, transcript, customer_id)",
    "        return _balance_answer(db, parsed, transcript, customer_id, language)",
    "handle balance",
)
sub(
    "        return _top_debtor_answer(db, parsed, transcript)",
    "        return _top_debtor_answer(db, parsed, transcript, language)",
    "handle top",
)
sub(
    "        return _daily_answer(db, parsed, transcript)",
    "        return _daily_answer(db, parsed, transcript, language=language)",
    "handle daily",
)
sub(
    '        raise ServiceError("empty_text", "Kuch sunai nahi diya. Phir se bolein ya likhein.", 422)',
    '        raise ServiceError("empty_text", tr(language, "err_empty_text"), 422)',
    "empty text",
)

# 10) manual proposal
sub(
    "    amount_rupees: Decimal,\n    transcript: str | None = None,\n) -> dict:",
    '    amount_rupees: Decimal,\n    transcript: str | None = None,\n    language: str = "hi-IN",\n) -> dict:',
    "manual signature",
)
sub(
    '        raise ServiceError("unknown_customer", "Yeh customer ledger mein nahi mila.", 404)',
    '        raise ServiceError("unknown_customer", tr(language, "err_unknown_customer"), 404)',
    "manual unknown customer",
)
sub(
    "    amount_paise = _validate_amount_paise(amount_rupees)",
    "    amount_paise = _validate_amount_paise(amount_rupees, language)",
    "manual validate",
)

# 11) confirmed response
sub(
    "def _confirmed_response(db: Session, pending: PendingTransaction, txn: Transaction, already: bool) -> dict:",
    'def _confirmed_response(\n    db: Session,\n    pending: PendingTransaction,\n    txn: Transaction,\n    already: bool,\n    language: str = "hi-IN",\n) -> dict:',
    "confirmed signature",
)
sub(
    """    if is_credit:
        message = f"{customer.name} ji ka {format_inr(txn.amount_paise)} udhaar likh diya. Ab baaki {format_inr(balance)} hai.\"""",
    f"""    if is_credit:
        message = tr(
            language,
            "confirmed_credit",
            name=customer.name,
            amount=format_inr(txn.amount_paise),
            balance=format_inr(balance),
        )""",
    "confirmed credit",
)
sub(
    """        message = (
            f"{customer.name} ji se {format_inr(txn.amount_paise)} jama ho gaye. "
            f"Ab {format_inr(-balance)} advance jama hai."
        )""",
    """        message = tr(
            language,
            "confirmed_advance",
            name=customer.name,
            amount=format_inr(txn.amount_paise),
            advance=format_inr(-balance),
        )""",
    "confirmed advance",
)
sub(
    '        message = f"{customer.name} ji se {format_inr(txn.amount_paise)} jama ho gaye. Ab baaki {format_inr(balance)} hai."',
    """        message = tr(
            language,
            "confirmed_payment",
            name=customer.name,
            amount=format_inr(txn.amount_paise),
            balance=format_inr(balance),
        )""",
    "confirmed payment",
)
sub(
    '        message = "Yeh transaction pehle hi save ho chuka hai. " + message\n        speech = "यह लेन-देन पहले ही सुरक्षित हो चुका है। " + speech',
    f"""        message = tr(language, "already_saved") + message
        speech = (
            "यह लेन-देन पहले ही सुरक्षित हो चुका है। " + speech
            if {HI}
            else message
        )""",
    "confirmed already",
)

# 12) confirm / cancel
sub(
    "def confirm_pending(db: Session, pending_id: str, acknowledge_overpayment: bool = False) -> dict:",
    'def confirm_pending(\n    db: Session,\n    pending_id: str,\n    acknowledge_overpayment: bool = False,\n    language: str = "hi-IN",\n) -> dict:',
    "confirm signature",
)
src = src.replace("_confirmed_response(db, pending, txn, already=True)", "_confirmed_response(db, pending, txn, True, language)")
src = src.replace("_confirmed_response(db, fresh, txn, already=True)", "_confirmed_response(db, fresh, txn, True, language)")
src = src.replace("_confirmed_response(db, pending, txn, already=False)", "_confirmed_response(db, pending, txn, False, language)")
sub(
    '        raise ServiceError("pending_not_found", "Yeh pending transaction nahi mila.", 404)',
    '        raise ServiceError("pending_not_found", tr(language, "err_pending_not_found"), 404)',
    "pending not found",
)
src = src.replace(
    '"Yeh confirmation expire ho gaya. Phir se bolein."', 'tr(language, "err_pending_expired")'
)
src = src.replace('"Yeh transaction cancel ho chuka hai."', 'tr(language, "err_pending_cancelled")')
src = src.replace('"Yeh transaction ab confirm nahi ho sakta."', 'tr(language, "err_pending_changed")')
src = src.replace(
    '"Payment baaki raqam se zyada hai. Advance jama karne ke liye haan karein."',
    'tr(language, "err_overpay_ack")',
)
sub(
    "def cancel_pending(db: Session, pending_id: str) -> dict:",
    'def cancel_pending(db: Session, pending_id: str, language: str = "hi-IN") -> dict:',
    "cancel signature",
)
sub(
    '"already_confirmed",\n            "Yeh transaction already save ho chuka hai, cancel nahi ho sakta.",',
    '"already_confirmed",\n            tr(language, "err_already_confirmed"),',
    "cancel already confirmed",
)
sub(
    '"message": "Transaction cancel hai. Ledger nahi badla."',
    '"message": tr(language, "cancel_already")',
    "cancel already msg",
)
sub(
    '"message": "Cancel kar diya. Ledger mein koi badlav nahi hua."',
    '"message": tr(language, "cancel_done")',
    "cancel done",
)

# 13) daily_summary
sub(
    "def daily_summary(db: Session, day: date | None = None) -> dict:",
    'def daily_summary(db: Session, day: date | None = None, language: str = "hi-IN") -> dict:',
    "daily signature",
)
sub(
    """    reminders = [
        f"{customer['name']} ji ka {customer['balance_text']} baaki hai — yaad dila sakte hain."
        for customer in top
    ]""",
    """    reminders = [
        tr(language, "reminder", name=customer["name"], amount=customer["balance_text"])
        for customer in top
    ]""",
    "daily reminders",
)
sub(
    """    reply = (
        f"Aaj {format_inr(credit)} ka udhaar diya aur {format_inr(payment)} jama hua. "
        f"Net {format_inr(net)} {('badha' if net >= 0 else 'ghata')}. "
        f"Kul baaki {format_inr(totals)} hai."
    )
    if not rows:
        reply = f"Aaj abhi tak koi transaction nahi hua. Kul baaki {format_inr(totals)} hai."
""",
    """    direction_key = "daily_direction_up" if net >= 0 else "daily_direction_down"
    reply = tr(
        language,
        "daily_reply",
        credit=format_inr(credit),
        payment=format_inr(payment),
        net=format_inr(net),
        direction=tr(language, direction_key),
        total=format_inr(totals),
    )
    if not rows:
        reply = tr(language, "daily_empty", total=format_inr(totals))
""",
    "daily reply",
)
sub(
    """    speech = (
        f"आज {hindi_rupee_words(credit)} का उधार दिया और {hindi_rupee_words(payment)} जमा हुआ। "
        f"कुल बकाया {hindi_rupee_words(totals)} है।"
    )
    if top:
        speech += f" सबसे ज़्यादा बकाया {top[0]['name']} जी का {hindi_rupee_words(top[0]['balance_paise'])} है。"""".replace("。", "।"),
    f"""    if {HI}:
        speech = (
            f"आज {{hindi_rupee_words(credit)}} का उधार दिया और {{hindi_rupee_words(payment)}} जमा हुआ। "
            f"कुल बकाया {{hindi_rupee_words(totals)}} है।"
        )
        if top:
            speech += f" सबसे ज़्यादा बकाया {{top[0]['name']}} जी का {{hindi_rupee_words(top[0]['balance_paise'])}} है।"
    else:
        speech = tr(
            language,
            "daily_speech",
            credit=format_inr(credit),
            payment=format_inr(payment),
            total=format_inr(totals),
        )""",
    "daily speech",
)

P.write_bytes(src.replace("\n", newline).encode("utf-8"))
print("services.py patched")
