"""Ledger and command services: parsing -> preview -> explicit confirmation.

Safety rules implemented here:

1.  Parsing and previewing never write to the ledger (pending rows are not
    transactions).
2.  A transaction row is only created after the shopkeeper confirms a specific
    pending action.
3.  Confirmation is atomic and idempotent. A pending action can create at most
    one transaction (unique ``pending_id``), so retries return the original
    result rather than double-posting.
4.  Balances are always derived from the transaction log.
5.  A payment larger than the outstanding balance requires an extra
    acknowledgement; it is never silently posted.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from config import settings
from models import Customer, PendingTransaction, Transaction
from money import format_inr, hindi_rupee_words, to_paise
from parser import (
    INTENT_ADD_CREDIT,
    INTENT_BALANCE_QUERY,
    INTENT_DAILY_SUMMARY,
    INTENT_RECORD_PAYMENT,
    INTENT_TOP_DEBTOR,
    TRANSACTION_INTENTS,
    ParsedCommand,
    canonical_name,
    detect_compound,
    name_similarity,
    normalize_name,
    parse_command,
    simplify_latin,
)

TYPE_CREDIT = "credit"
TYPE_PAYMENT = "payment"


class ServiceError(Exception):
    """Expected, user-safe error. ``code`` is stable for the frontend."""

    def __init__(self, code: str, message: str, status_code: int = 400, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.hint = hint


# ---------------------------------------------------------------------------
# Time helpers (store UTC, display IST)
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite friendly, no local-time ambiguity)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def as_ist(value: datetime) -> datetime:
    return as_aware_utc(value).astimezone(settings.ist)


def iso_ist(value: datetime) -> str:
    return as_ist(value).isoformat()


def ist_day_bounds(day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=settings.ist)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=settings.ist)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def today_ist() -> date:
    return datetime.now(settings.ist).date()


# ---------------------------------------------------------------------------
# Balances
# ---------------------------------------------------------------------------

_BALANCE_EXPR = func.coalesce(
    func.sum(
        case(
            (Transaction.type == TYPE_CREDIT, Transaction.amount_paise),
            else_=-Transaction.amount_paise,
        )
    ),
    0,
)


def get_balance_paise(db: Session, customer_id: int) -> int:
    value = db.scalar(select(_BALANCE_EXPR).where(Transaction.customer_id == customer_id))
    return int(value or 0)


def get_all_balances(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(Transaction.customer_id, _BALANCE_EXPR.label("balance")).group_by(Transaction.customer_id)
    ).all()
    return {int(row.customer_id): int(row.balance) for row in rows}


def serialize_customer(customer: Customer, balance_paise: int) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "balance_paise": balance_paise,
        "balance_text": format_inr(balance_paise),
        "is_sample": bool(customer.is_sample),
    }


def serialize_transaction(txn: Transaction, customer: Customer | None = None) -> dict:
    return {
        "id": txn.id,
        "customer_id": txn.customer_id,
        "customer_name": customer.name if customer else None,
        "type": txn.type,
        "type_label": "Udhaar diya" if txn.type == TYPE_CREDIT else "Payment mila",
        "amount_paise": txn.amount_paise,
        "amount_text": format_inr(txn.amount_paise),
        "created_at": iso_ist(txn.created_at),
        "transcript": txn.transcript,
        "source": txn.source,
        "balance_after_paise": txn.balance_after_paise,
        "balance_after_text": format_inr(txn.balance_after_paise),
        "is_sample": bool(txn.is_sample),
    }


# ---------------------------------------------------------------------------
# Customer resolution
# ---------------------------------------------------------------------------


def create_customer(db: Session, name: str) -> dict:
    """Explicitly add a customer. Only ever called from a user action.

    An uncertain transcript never creates a customer automatically.
    """
    clean = " ".join((name or "").split())
    if len(clean) < 2:
        raise ServiceError("invalid_customer_name", "Customer ka naam kam se kam 2 letters ka ho.", 422)
    if len(clean) > 80:
        raise ServiceError("invalid_customer_name", "Naam 80 letters se chhota rakhein.", 422)
    if re.search(r"\d", clean):
        raise ServiceError(
            "invalid_customer_name",
            "Naam mein number nahi daalein (privacy aur saaf matching ke liye).",
            422,
        )
    if not re.search(r"[A-Za-z\u0900-\u097F]", clean):
        raise ServiceError("invalid_customer_name", "Naam mein letters hone chahiye.", 422)

    normalized = canonical_name(clean)
    if not normalized:
        raise ServiceError("invalid_customer_name", "Naam sahi nahi hai.", 422)
    # Duplicate detection compares canonical keys recomputed from the stored
    # name, not just the cached column: rows written before the key was folded
    # (e.g. "सुनीता" -> "suneetaa") must still collide with "Sunita", otherwise
    # one person ends up with two ledger rows and split balances.
    existing = None
    for customer in db.scalars(select(Customer)).all():
        if canonical_name(customer.name) == normalized or customer.name_normalized == normalized:
            existing = customer
            break
    if existing is not None:
        raise ServiceError(
            "customer_exists",
            f"{existing.name} pehle se ledger mein hai.",
            409,
            hint="Usi customer ka naam chunein.",
        )

    customer = Customer(
        name=clean,
        name_normalized=normalized,
        is_sample=False,
        created_at=utcnow(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return serialize_customer(customer, 0)


def list_customers(db: Session) -> list[dict]:
    balances = get_all_balances(db)
    customers = db.scalars(select(Customer).order_by(Customer.name)).all()
    return [serialize_customer(customer, balances.get(customer.id, 0)) for customer in customers]


def _matches_from_text(db: Session, text: str) -> list[Customer]:
    """Find known customer names mentioned anywhere in the transcript."""
    haystack = f" {canonical_name(text)} "
    found: list[Customer] = []
    for customer in db.scalars(select(Customer)).all():
        needle = canonical_name(customer.name)
        if needle and f" {needle} " in haystack:
            found.append(customer)
    return found


def resolve_customer(
    db: Session, name: str | None, text: str = "", customer_id: int | None = None
) -> tuple[Customer | None, list[dict], str]:
    """Return ``(customer, suggestions, status)``.

    status is one of ``resolved``, ``missing``, ``no_match``, ``ambiguous``.
    """
    if customer_id is not None:
        customer = db.get(Customer, customer_id)
        if customer is None:
            raise ServiceError("unknown_customer", "Yeh customer ledger mein nahi mila.", 404)
        return customer, [], "resolved"

    balances = get_all_balances(db)
    customers = db.scalars(select(Customer)).all()

    if name:
        normalized = canonical_name(name)
        if normalized:
            # Exact key first: script- and honorific-insensitive, recomputed
            # from the stored name so pre-fold rows still match.
            exact = [
                customer
                for customer in customers
                if canonical_name(customer.name) == normalized
                or customer.name_normalized == normalized
            ]
            if len(exact) == 1:
                return exact[0], [], "resolved"
            if len(exact) > 1:
                # Two rows share the same key — never guess between them.
                suggestions = [
                    {**serialize_customer(customer, balances.get(customer.id, 0)), "score": 1.0}
                    for customer in exact[:3]
                ]
                return None, suggestions, "ambiguous"
            scored = sorted(
                ((name_similarity(name, customer.name), customer) for customer in customers),
                key=lambda item: item[0],
                reverse=True,
            )
            scored = [(score, customer) for score, customer in scored if score >= 0.62]
            if scored:
                best_score, best_customer = scored[0]
                second_score = scored[1][0] if len(scored) > 1 else 0.0
                margin = best_score - second_score
                # Auto-resolve only when the best candidate is near-certain *and*
                # clearly ahead.  A close runner-up ("Sunita" vs "Suneeta") means
                # we genuinely do not know who was meant — ask, do not guess.
                close_runner_up = second_score >= 0.80 and margin < 0.10
                if best_score >= 0.95 and margin >= 0.06 and not close_runner_up:
                    return best_customer, [], "resolved"
                suggestions = [
                    {
                        **serialize_customer(customer, balances.get(customer.id, 0)),
                        "score": score,
                    }
                    for score, customer in scored[:3]
                ]
                return None, suggestions, "ambiguous" if len(suggestions) > 1 else "no_match"
            return None, [], "no_match"

    # No parsed name: look for exactly one known customer mentioned in the text.
    mentioned = _matches_from_text(db, text)
    if len(mentioned) == 1:
        return mentioned[0], [], "resolved"
    if len(mentioned) > 1:
        suggestions = [
            {**serialize_customer(customer, balances.get(customer.id, 0)), "score": 0.9}
            for customer in mentioned[:3]
        ]
        return None, suggestions, "ambiguous"
    return None, [], "missing"


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def _parser_payload(parsed: ParsedCommand) -> dict:
    payload = parsed.to_dict()
    payload["amount_text"] = format_inr(to_paise(parsed.amount_rupees)) if parsed.amount_rupees else None
    return payload


def _base_response(kind: str, transcript: str, parsed: ParsedCommand, message: str, speech: str) -> dict:
    return {
        "kind": kind,
        "transcript": transcript,
        "message": message,
        "speech_text": speech,
        "parser": _parser_payload(parsed),
        "proposal": None,
        "clarification": None,
        "answer": None,
    }


def _clarification(
    transcript: str,
    parsed: ParsedCommand,
    needs: list[str],
    question: str,
    speech: str,
    suggestions: list[dict] | None = None,
    examples: list[str] | None = None,
) -> dict:
    response = _base_response("clarification", transcript, parsed, question, speech)
    response["clarification"] = {
        "needs": needs,
        "question": question,
        "customers": suggestions or [],
        "examples": examples or [],
    }
    return response


_INTENT_LABELS = {
    INTENT_ADD_CREDIT: "Udhaar likhna",
    INTENT_RECORD_PAYMENT: "Payment lena",
    INTENT_BALANCE_QUERY: "Balance poochna",
    INTENT_TOP_DEBTOR: "Sabse zyada udhaar",
    INTENT_DAILY_SUMMARY: "Aaj ka hisaab",
}


def _compound_clarification(
    transcript: str,
    parsed: ParsedCommand,
    clauses: list[tuple[str, ParsedCommand]],
) -> dict:
    """Two instructions in one breath — ask for them one at a time.

    Nothing is executed and nothing is dropped silently: every detected clause
    is echoed back so the shopkeeper can see that both halves were understood
    and must be confirmed separately.
    """
    question = (
        f"Ek hi baat mein {len(clauses)} kaam sunai diya. "
        "Ek-ek karke bolein — pehla kaam bataein, uske baad doosra."
    )
    speech = (
        f"एक ही बात में {len(clauses)} काम सुनाई दिए। "
        "एक-एक करके बोलें — पहला काम बताएँ, उसके बाद दूसरा।"
    )
    response = _clarification(
        transcript,
        parsed,
        ["compound"],
        question,
        speech,
        examples=_EXAMPLE_COMMANDS,
    )
    response["clarification"]["commands"] = [
        {
            "text": clause_text,
            "intent": clause.intent,
            "intent_label": _INTENT_LABELS.get(clause.intent, "Samajh nahi aaya"),
            "amount_text": (
                format_inr(to_paise(clause.amount_rupees)) if clause.amount_rupees else None
            ),
            "customer_name": clause.customer_name,
        }
        for clause_text, clause in clauses
    ]
    return response


_EXAMPLE_COMMANDS = [
    "Ramesh ko dedh sau rupaye ka udhaar likh do",
    "Sunita ne do sau rupaye wapas kar diye",
    "Mohan ka kitna udhaar baaki hai",
    "Sabse zyada udhaar kis customer ka hai",
    "Aaj ka poora hisaab batao",
]


def _balance_phrase(balance_paise: int) -> tuple[str, str]:
    """Return (Hinglish, Hindi speech) phrase for a possibly negative balance."""
    if balance_paise > 0:
        return f"{format_inr(balance_paise)} baaki hai", f"{hindi_rupee_words(balance_paise)} बाकी है"
    if balance_paise < 0:
        return (
            f"{format_inr(-balance_paise)} advance jama hai",
            f"{hindi_rupee_words(-balance_paise)} एडवांस जमा है",
        )
    return "koi udhaar baaki nahi hai", "कोई उधार बाकी नहीं है"


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


def _validate_amount_paise(amount_rupees: Decimal | None) -> int:
    if amount_rupees is None:
        raise ServiceError("missing_amount", "Amount nahi mila. Kitne rupaye ka udhaar hai?", 422)
    try:
        amount = Decimal(amount_rupees)
    except (InvalidOperation, TypeError, ValueError):
        raise ServiceError("invalid_amount", "Amount sahi number nahi hai.", 422)
    if amount <= 0:
        raise ServiceError("invalid_amount", "Amount zero se bada hona chahiye.", 422)
    if amount > Decimal(settings.max_amount_rupees):
        raise ServiceError(
            "amount_too_large",
            f"Amount ₹{settings.max_amount_rupees:,} se zyada nahi ho sakta.",
            422,
        )
    paise = to_paise(amount)
    if paise <= 0:
        raise ServiceError("invalid_amount", "Amount zero se bada hona chahiye.", 422)
    return paise


def create_pending(
    db: Session,
    customer: Customer,
    txn_type: str,
    amount_paise: int,
    transcript: str,
    source: str,
    parser_info: dict,
) -> dict:
    if txn_type not in {TYPE_CREDIT, TYPE_PAYMENT}:
        raise ServiceError("invalid_type", "Transaction type sahi nahi hai.", 422)
    if amount_paise <= 0:
        raise ServiceError("invalid_amount", "Amount zero se bada hona chahiye.", 422)

    balance_before = get_balance_paise(db, customer.id)
    delta = amount_paise if txn_type == TYPE_CREDIT else -amount_paise
    balance_after = balance_before + delta
    requires_ack = txn_type == TYPE_PAYMENT and amount_paise > balance_before

    # Re-sending the *exact same* instruction supersedes the earlier identical
    # preview.  A double-tap of "Bhejein" (or a retry after a slow request) then
    # cannot post the same entry twice: the older preview is cancelled and a
    # stale confirm gets 409 instead of writing a duplicate row.  Deliberately
    # scoped to the same customer + same transcript, so genuinely different
    # entries (or a second, distinct instruction) keep their own preview and are
    # never silently dropped.
    db.execute(
        update(PendingTransaction)
        .where(
            PendingTransaction.customer_id == customer.id,
            PendingTransaction.status == "pending",
            PendingTransaction.transcript == transcript,
        )
        .values(status="cancelled")
    )

    now = utcnow()
    pending = PendingTransaction(
        customer_id=customer.id,
        type=txn_type,
        amount_paise=amount_paise,
        transcript=transcript,
        source=source,
        status="pending",
        created_at=now,
        expires_at=now + timedelta(minutes=settings.pending_ttl_minutes),
        balance_before_paise=balance_before,
        requires_overpayment_ack=requires_ack,
        parser_json=json.dumps(parser_info, ensure_ascii=False, default=str),
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)

    is_credit = txn_type == TYPE_CREDIT
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
        speech += " ध्यान दें, यह रकम बकाया से ज़्यादा है, इसलिए एडवांस जमा होगा।"

    return {
        "pending_id": pending.id,
        "customer": serialize_customer(customer, balance_before),
        "type": txn_type,
        "type_label": "Udhaar (credit)" if is_credit else "Payment (jama)",
        "amount_paise": amount_paise,
        "amount_text": format_inr(amount_paise),
        "balance_before_paise": balance_before,
        "balance_before_text": format_inr(balance_before),
        "balance_after_paise": balance_after,
        "balance_after_text": format_inr(balance_after),
        "requires_overpayment_ack": requires_ack,
        "expires_at": iso_ist(pending.expires_at),
        "transcript": transcript,
        "message": message,
        "speech_text": speech,
    }


def _transaction_proposal(
    db: Session,
    parsed: ParsedCommand,
    transcript: str,
    source: str,
    customer_id: int | None,
) -> dict:
    amount_paise = _validate_amount_paise(parsed.amount_rupees)
    if len([code for code in parsed.ambiguity if code in {"multiple_amounts", "amount_needs_review"}]) > 0:
        raise ServiceError(
            "ambiguous_amount",
            "Ek se zyada amount mile. Sahi amount likh kar bhejein.",
            422,
        )

    customer, suggestions, status = resolve_customer(db, parsed.customer_name, transcript, customer_id)
    if customer is None:
        if len(suggestions) == 1:
            target = suggestions[0]["name"]
            return _clarification(
                transcript,
                parsed,
                ["customer"],
                f'"{parsed.customer_name}" se matlab {target} ji hai? Sahi customer chunein.',
                "क्या आप इसी ग्राहक की बात कर रहे हैं? सही नाम चुनें।",
                suggestions,
            )
        if status == "ambiguous":
            return _clarification(
                transcript,
                parsed,
                ["customer"],
                "Ek se zyada customer match hue. Sahi naam chunein.",
                "एक से ज़्यादा ग्राहक मिले। सही नाम चुनें।",
                suggestions,
            )
        if status == "no_match":
            return _clarification(
                transcript,
                parsed,
                ["customer"],
                f'"{parsed.customer_name}" naam ka customer nahi mila. Naya customer banayein ya sahi naam chunein.',
                "यह नाम का ग्राहक नहीं मिला। नया ग्राहक बनाएँ या सही नाम चुनें।",
                suggestions,
            )
        return _clarification(
            transcript,
            parsed,
            ["customer"],
            "Customer ka naam kaun hai? Neeche se chunein ya naam bolein.",
            "ग्राहक का नाम कौन है? नीचे से चुनें।",
            suggestions,
        )

    txn_type = TYPE_CREDIT if parsed.intent == INTENT_ADD_CREDIT else TYPE_PAYMENT
    proposal = create_pending(
        db, customer, txn_type, amount_paise, transcript, source, _parser_payload(parsed)
    )
    if "assumed_dedh" in parsed.ambiguity:
        # Surface the STT assumption on the card before the shopkeeper confirms.
        proposal["message"] += (
            ' Dhyan dein: transcript mein "de do sau" tha, ise "dedh sau" maana gaya.'
            ' Galat ho toh "Sahi karein" dabayein.'
        )
        proposal["warning"] = "assumed_dedh"
    response = _base_response("proposal", transcript, parsed, proposal["message"], proposal["speech_text"])
    response["proposal"] = proposal
    return response


def _balance_answer(db: Session, parsed: ParsedCommand, transcript: str, customer_id: int | None) -> dict:
    customer, suggestions, status = resolve_customer(db, parsed.customer_name, transcript, customer_id)
    if customer is None:
        if status == "missing":
            question = "Kis customer ka balance dekhna hai?"
            speech = "किस ग्राहक का बकाया देखना है?"
        elif status == "ambiguous":
            question = "Kaunsa customer? Ek naam chunein."
            speech = "कौन से ग्राहक का बकाया? नीचे से नाम चुनें।"
        else:
            question = f'"{parsed.customer_name}" naam ka customer nahi mila. Sahi customer chunein.'
            speech = "यह नाम का ग्राहक नहीं मिला। सही ग्राहक चुनें।"
        return _clarification(transcript, parsed, ["customer"], question, speech, suggestions)

    balance = get_balance_paise(db, customer.id)
    phrase, speech_phrase = _balance_phrase(balance)
    recent = db.scalars(
        select(Transaction)
        .where(Transaction.customer_id == customer.id)
        .order_by(Transaction.created_at.desc())
        .limit(5)
    ).all()
    message = f"{customer.name} ji ka {phrase}."
    speech = f"{customer.name} जी का {speech_phrase}।"
    response = _base_response("answer", transcript, parsed, message, speech)
    response["answer"] = {
        "kind": "balance",
        "customer": serialize_customer(customer, balance),
        "balance_paise": balance,
        "balance_text": format_inr(balance),
        "transactions": [serialize_transaction(txn, customer) for txn in recent],
    }
    return response


def _top_debtor_answer(db: Session, parsed: ParsedCommand, transcript: str) -> dict:
    top = top_debtors(db, limit=5)
    if not top:
        message = "Abhi kisi customer ka udhaar baaki nahi hai."
        speech = "अभी किसी ग्राहक का उधार बाकी नहीं है।"
    else:
        first = top[0]
        message = f"Sabse zyada udhaar {first['name']} ji ka {first['balance_text']} hai."
        speech = (
            f"सबसे ज़्यादा उधार {first['name']} जी का "
            f"{hindi_rupee_words(first['balance_paise'])} है।"
        )
    response = _base_response("answer", transcript, parsed, message, speech)
    response["answer"] = {"kind": "top_debtor", "customers": top}
    return response


def _daily_answer(db: Session, parsed: ParsedCommand, transcript: str, day: date | None = None) -> dict:
    summary = daily_summary(db, day)
    response = _base_response("answer", transcript, parsed, summary["reply_text"], summary["speech_text"])
    response["answer"] = {"kind": "daily_summary", "summary": summary}
    return response


def handle_command(
    db: Session,
    text: str,
    source: str = "text",
    customer_id: int | None = None,
) -> dict:
    """Parse and preview. Never posts a transaction."""
    transcript = (text or "").strip()
    if not transcript:
        raise ServiceError("empty_text", "Kuch sunai nahi diya. Phir se bolein ya likhein.", 422)

    parsed = parse_command(transcript)

    # Two instructions in one utterance must never collapse into one action.
    compound = detect_compound(transcript)
    if compound:
        return _compound_clarification(transcript, parsed, compound)

    if parsed.intent in TRANSACTION_INTENTS:
        # An amount is mandatory; the customer can still be resolved from the
        # transcript or picked by the shopkeeper afterwards.
        if "multiple_amounts" in parsed.ambiguity:
            return _clarification(
                transcript,
                parsed,
                ["amount"],
                "Ek se zyada amount mile. Sahi amount likh kar bhejein.",
                "एक से ज़्यादा रकम मिली। सही रकम लिखकर भेजें।",
                examples=_EXAMPLE_COMMANDS,
            )
        if parsed.amount_rupees is None or "invalid_amount" in parsed.ambiguity:
            question = (
                "Amount sahi nahi hai. Zero se bada number bolein."
                if "invalid_amount" in parsed.ambiguity
                else "Kitne rupaye? Jaise: “Ramesh ko dedh sau ka udhaar”"
            )
            speech = (
                "रकम सही नहीं है। शून्य से बड़ी रकम बताएँ।"
                if "invalid_amount" in parsed.ambiguity
                else "कितने रुपये? जैसे रमेश को डेढ़ सौ का उधार।"
            )
            return _clarification(
                transcript, parsed, ["amount"], question, speech, examples=_EXAMPLE_COMMANDS
            )
        if "conflicting_intent" in parsed.ambiguity:
            return _clarification(
                transcript,
                parsed,
                ["intent"],
                "Ek hi vaaky mein udhaar aur balance sawal dono hain. Pehle transaction bolein, phir balance poochein.",
                "एक ही वाक्य में उधार और बकाया दोनों हैं। पहले लेन-देन बताएँ।",
                examples=_EXAMPLE_COMMANDS,
            )
        return _transaction_proposal(db, parsed, transcript, source, customer_id)

    if parsed.intent == INTENT_BALANCE_QUERY:
        return _balance_answer(db, parsed, transcript, customer_id)

    if parsed.intent == INTENT_TOP_DEBTOR:
        return _top_debtor_answer(db, parsed, transcript)

    if parsed.intent == INTENT_DAILY_SUMMARY:
        return _daily_answer(db, parsed, transcript)

    return _clarification(
        transcript,
        parsed,
        ["intent"],
        "Samajh nahi aaya. Aise bolein: “Ramesh ko dedh sau ka udhaar likh do.”",
        "समझ नहीं आया। ऐसे बोलें: रमेश को डेढ़ सौ का उधार लिख दो।",
        examples=_EXAMPLE_COMMANDS,
    )


def manual_proposal(
    db: Session,
    customer_id: int,
    txn_type: str,
    amount_rupees: Decimal,
    transcript: str | None = None,
) -> dict:
    """Correct-details path. Still requires explicit confirmation."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ServiceError("unknown_customer", "Yeh customer ledger mein nahi mila.", 404)
    if txn_type not in {TYPE_CREDIT, TYPE_PAYMENT}:
        raise ServiceError("invalid_type", "Transaction type sahi nahi hai.", 422)
    amount_paise = _validate_amount_paise(amount_rupees)
    text = (transcript or "").strip() or f"Manual entry: {customer.name} {format_inr(amount_paise)} {txn_type}"
    parser_info = {
        "intent": INTENT_ADD_CREDIT if txn_type == TYPE_CREDIT else INTENT_RECORD_PAYMENT,
        "manual": True,
        "amount_rupees": str(amount_rupees),
        "customer_name": customer.name,
    }
    proposal = create_pending(db, customer, txn_type, amount_paise, text, "manual", parser_info)
    response = _base_response("proposal", text, parse_command(text), proposal["message"], proposal["speech_text"])
    response["parser"] = parser_info
    response["proposal"] = proposal
    return response


# ---------------------------------------------------------------------------
# Confirmation / cancellation
# ---------------------------------------------------------------------------


def _confirmed_response(db: Session, pending: PendingTransaction, txn: Transaction, already: bool) -> dict:
    customer = txn.customer or db.get(Customer, txn.customer_id)
    balance = get_balance_paise(db, txn.customer_id)
    is_credit = txn.type == TYPE_CREDIT
    if is_credit:
        message = f"{customer.name} ji ka {format_inr(txn.amount_paise)} udhaar likh diya. Ab baaki {format_inr(balance)} hai."
        speech = (
            f"{customer.name} जी का {hindi_rupee_words(txn.amount_paise)} का उधार लिख दिया गया है। "
            f"अब बकाया {hindi_rupee_words(balance)} है।"
        )
    elif balance < 0:
        message = (
            f"{customer.name} ji se {format_inr(txn.amount_paise)} jama ho gaye. "
            f"Ab {format_inr(-balance)} advance jama hai."
        )
        speech = (
            f"{customer.name} जी से {hindi_rupee_words(txn.amount_paise)} जमा हो गए हैं। "
            f"अब {hindi_rupee_words(-balance)} एडवांस जमा है।"
        )
    else:
        message = f"{customer.name} ji se {format_inr(txn.amount_paise)} jama ho gaye. Ab baaki {format_inr(balance)} hai."
        speech = (
            f"{customer.name} जी से {hindi_rupee_words(txn.amount_paise)} जमा हो गए हैं। "
            f"अब बकाया {hindi_rupee_words(balance)} है।"
        )
    if already:
        message = "Yeh transaction pehle hi save ho chuka hai. " + message
        speech = "यह लेन-देन पहले ही सुरक्षित हो चुका है। " + speech

    return {
        "kind": "confirmed",
        "already_confirmed": already,
        "transaction": serialize_transaction(txn, customer),
        "customer": serialize_customer(customer, balance),
        "message": message,
        "speech_text": speech,
    }


def confirm_pending(db: Session, pending_id: str, acknowledge_overpayment: bool = False) -> dict:
    """Atomically post a pending action exactly once."""
    pending = db.get(PendingTransaction, pending_id)
    if pending is None:
        raise ServiceError("pending_not_found", "Yeh pending transaction nahi mila.", 404)

    if pending.status == "confirmed":
        txn = db.get(Transaction, pending.confirmed_transaction_id) if pending.confirmed_transaction_id else None
        if txn is None:  # pragma: no cover - corrupt state guard
            raise ServiceError("inconsistent", "Transaction record nahi mila.", 500)
        if txn.customer is None:
            txn.customer = db.get(Customer, txn.customer_id)
        return _confirmed_response(db, pending, txn, already=True)

    if pending.status == "cancelled":
        raise ServiceError("pending_cancelled", "Yeh transaction cancel ho chuka hai.", 409)
    if pending.status == "expired":
        raise ServiceError("pending_expired", "Yeh confirmation expire ho gaya. Phir se bolein.", 409)
    if pending.expires_at <= utcnow():
        pending.status = "expired"
        db.commit()
        raise ServiceError("pending_expired", "Yeh confirmation expire ho gaya. Phir se bolein.", 409)

    customer = db.get(Customer, pending.customer_id)
    if customer is None:  # pragma: no cover
        raise ServiceError("unknown_customer", "Customer nahi mila.", 409)

    if pending.requires_overpayment_ack and not acknowledge_overpayment:
        raise ServiceError(
            "overpayment_ack_required",
            "Payment baaki raqam se zyada hai. Advance jama karne ke liye haan karein.",
            409,
            hint="confirm with acknowledge_overpayment=true",
        )

    now = utcnow()
    claimed = db.execute(
        update(PendingTransaction)
        .where(PendingTransaction.id == pending_id, PendingTransaction.status == "pending")
        .values(status="confirmed", confirmed_at=now)
    ).rowcount
    if claimed != 1:
        db.rollback()
        db.expire_all()
        fresh = db.get(PendingTransaction, pending_id)
        if fresh and fresh.status == "confirmed" and fresh.confirmed_transaction_id:
            txn = db.get(Transaction, fresh.confirmed_transaction_id)
            if txn and txn.customer is None:
                txn.customer = db.get(Customer, txn.customer_id)
            return _confirmed_response(db, fresh, txn, already=True)
        raise ServiceError("pending_changed", "Yeh transaction ab confirm nahi ho sakta.", 409)

    balance_before = get_balance_paise(db, customer.id)
    # Re-check overpayment against the balance at commit time (a concurrent
    # payment may have reduced it since the preview).
    if pending.type == TYPE_PAYMENT and pending.amount_paise > balance_before and not acknowledge_overpayment:
        db.rollback()
        db.expire_all()
        fresh = db.get(PendingTransaction, pending_id)
        if fresh is not None and fresh.status == "pending":
            fresh.requires_overpayment_ack = True
            db.commit()
        raise ServiceError(
            "overpayment_ack_required",
            "Payment baaki raqam se zyada hai. Advance jama karne ke liye haan karein.",
            409,
            hint="confirm with acknowledge_overpayment=true",
        )

    delta = pending.amount_paise if pending.type == TYPE_CREDIT else -pending.amount_paise
    txn = Transaction(
        customer_id=customer.id,
        type=pending.type,
        amount_paise=pending.amount_paise,
        created_at=now,
        transcript=pending.transcript,
        source=pending.source,
        pending_id=pending.id,
        balance_after_paise=balance_before + delta,
    )
    db.add(txn)
    db.flush()
    db.execute(
        update(PendingTransaction)
        .where(PendingTransaction.id == pending_id)
        .values(confirmed_transaction_id=txn.id)
    )
    db.commit()
    db.refresh(txn)
    txn.customer = customer
    return _confirmed_response(db, pending, txn, already=False)


def cancel_pending(db: Session, pending_id: str) -> dict:
    pending = db.get(PendingTransaction, pending_id)
    if pending is None:
        raise ServiceError("pending_not_found", "Yeh pending transaction nahi mila.", 404)
    if pending.status == "confirmed":
        raise ServiceError(
            "already_confirmed",
            "Yeh transaction already save ho chuka hai, cancel nahi ho sakta.",
            409,
        )
    if pending.status == "cancelled":
        return {"kind": "cancelled", "pending_id": pending_id, "already": True,
                "message": "Transaction cancel hai. Ledger nahi badla."}
    changed = db.execute(
        update(PendingTransaction)
        .where(PendingTransaction.id == pending_id, PendingTransaction.status == "pending")
        .values(status="cancelled")
    ).rowcount
    db.commit()
    if changed != 1:
        raise ServiceError("pending_changed", "Yeh transaction cancel nahi ho sakta.", 409)
    return {
        "kind": "cancelled",
        "pending_id": pending_id,
        "already": False,
        "message": "Cancel kar diya. Ledger mein koi badlav nahi hua.",
    }


def get_pending(db: Session, pending_id: str) -> dict:
    pending = db.get(PendingTransaction, pending_id)
    if pending is None:
        raise ServiceError("pending_not_found", "Yeh pending transaction nahi mila.", 404)
    customer = db.get(Customer, pending.customer_id)
    current_balance = get_balance_paise(db, pending.customer_id) if customer else 0
    return {
        "pending_id": pending.id,
        "status": pending.status,
        "type": pending.type,
        "amount_paise": pending.amount_paise,
        "amount_text": format_inr(pending.amount_paise),
        "customer": serialize_customer(customer, current_balance) if customer else None,
        "balance_before_text": format_inr(pending.balance_before_paise),
        "requires_overpayment_ack": pending.requires_overpayment_ack,
        "expires_at": iso_ist(pending.expires_at),
        "created_at": iso_ist(pending.created_at),
        "confirmed_transaction_id": pending.confirmed_transaction_id,
    }


# ---------------------------------------------------------------------------
# Dashboard / history / summaries
# ---------------------------------------------------------------------------


def dashboard(db: Session) -> dict:
    balances = get_all_balances(db)
    total_outstanding = sum(balances.values())
    customer_count = db.scalar(select(func.count(Customer.id))) or 0
    transaction_count = db.scalar(select(func.count(Transaction.id))) or 0

    day = today_ist()
    start, end = ist_day_bounds(day)
    today_rows = db.execute(
        select(Transaction.type, func.coalesce(func.sum(Transaction.amount_paise), 0))
        .where(Transaction.created_at >= start, Transaction.created_at < end)
        .group_by(Transaction.type)
    ).all()
    sums = {row[0]: int(row[1]) for row in today_rows}
    credit = sums.get(TYPE_CREDIT, 0)
    payment = sums.get(TYPE_PAYMENT, 0)
    net = credit - payment

    today_count = db.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.created_at >= start, Transaction.created_at < end
        )
    ) or 0
    sample_rows = db.scalar(select(func.count(Customer.id)).where(Customer.is_sample.is_(True))) or 0

    return {
        "total_outstanding_paise": total_outstanding,
        "total_outstanding_text": format_inr(total_outstanding),
        "today_credit_paise": credit,
        "today_credit_text": format_inr(credit),
        "today_payment_paise": payment,
        "today_payment_text": format_inr(payment),
        "today_net_paise": net,
        "today_net_text": format_inr(net),
        "today_transaction_count": int(today_count),
        "customer_count": int(customer_count),
        "transaction_count": int(transaction_count),
        "sample_data": bool(sample_rows),
        "today_date": day.isoformat(),
        "server_time_ist": datetime.now(settings.ist).isoformat(),
    }


def list_transactions(db: Session, limit: int = 50, customer_id: int | None = None) -> list[dict]:
    stmt = (
        select(Transaction, Customer)
        .join(Customer, Transaction.customer_id == Customer.id)
        .order_by(Transaction.created_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    if customer_id is not None:
        stmt = stmt.where(Transaction.customer_id == customer_id)
    rows = db.execute(stmt).all()
    return [serialize_transaction(txn, customer) for txn, customer in rows]


def top_debtors(db: Session, limit: int = 5) -> list[dict]:
    balances = get_all_balances(db)
    customers = db.scalars(select(Customer)).all()
    ranked = [
        serialize_customer(customer, balances.get(customer.id, 0))
        for customer in customers
        if balances.get(customer.id, 0) > 0
    ]
    ranked.sort(key=lambda item: item["balance_paise"], reverse=True)
    return ranked[: max(1, min(limit, 20))]


def daily_summary(db: Session, day: date | None = None) -> dict:
    target = day or today_ist()
    start, end = ist_day_bounds(target)
    rows = db.execute(
        select(Transaction.type, func.coalesce(func.sum(Transaction.amount_paise), 0), func.count(Transaction.id))
        .where(Transaction.created_at >= start, Transaction.created_at < end)
        .group_by(Transaction.type)
    ).all()
    sums = {row[0]: int(row[1]) for row in rows}
    counts = {row[0]: int(row[2]) for row in rows}
    credit = sums.get(TYPE_CREDIT, 0)
    payment = sums.get(TYPE_PAYMENT, 0)
    net = credit - payment
    totals = get_balance_paise_total(db)
    top = top_debtors(db, limit=3)

    reminders = [
        f"{customer['name']} ji ka {customer['balance_text']} baaki hai — yaad dila sakte hain."
        for customer in top
    ]

    reply = (
        f"Aaj {format_inr(credit)} ka udhaar diya aur {format_inr(payment)} jama hua. "
        f"Net {format_inr(net)} {('badha' if net >= 0 else 'ghata')}. "
        f"Kul baaki {format_inr(totals)} hai."
    )
    if not rows:
        reply = f"Aaj abhi tak koi transaction nahi hua. Kul baaki {format_inr(totals)} hai."

    speech = (
        f"आज {hindi_rupee_words(credit)} का उधार दिया और {hindi_rupee_words(payment)} जमा हुआ। "
        f"कुल बकाया {hindi_rupee_words(totals)} है।"
    )
    if top:
        speech += f" सबसे ज़्यादा बकाया {top[0]['name']} जी का {hindi_rupee_words(top[0]['balance_paise'])} है।"

    return {
        "date": target.isoformat(),
        "date_label": target.strftime("%d %b %Y"),
        "credit_paise": credit,
        "credit_text": format_inr(credit),
        "payment_paise": payment,
        "payment_text": format_inr(payment),
        "net_paise": net,
        "net_text": format_inr(net),
        "total_outstanding_paise": totals,
        "total_outstanding_text": format_inr(totals),
        "credit_count": counts.get(TYPE_CREDIT, 0),
        "payment_count": counts.get(TYPE_PAYMENT, 0),
        "transaction_count": counts.get(TYPE_CREDIT, 0) + counts.get(TYPE_PAYMENT, 0),
        "top_debtors": top,
        "reminders": reminders,
        "reply_text": reply,
        "speech_text": speech,
    }


def get_balance_paise_total(db: Session) -> int:
    value = db.scalar(select(_BALANCE_EXPR))
    return int(value or 0)
