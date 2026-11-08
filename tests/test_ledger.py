"""Ledger safety: balances, confirmation, idempotency, overpayment, summaries."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from conftest import make_customer, post_entry
from models import PendingTransaction, Transaction
from services import (
    ServiceError,
    cancel_pending,
    confirm_pending,
    daily_summary,
    dashboard,
    get_balance_paise,
    handle_command,
    ist_day_bounds,
    manual_proposal,
    today_ist,
    top_debtors,
    utcnow,
)


def count(db, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def create_pending_entry(db, customer, txn_type: str, rupees: str):
    response = handle_command(
        db,
        f"{customer.name} ko {rupees} rupaye ka "
        + ("udhaar likh do" if txn_type == "credit" else "payment jama karo"),
    )
    assert response["kind"] == "proposal", response
    return response["proposal"]


# ---------------------------------------------------------------------------
# Balance arithmetic
# ---------------------------------------------------------------------------


def test_credit_increases_outstanding(db):
    ramesh = make_customer(db, "Ramesh")
    assert get_balance_paise(db, ramesh.id) == 0
    post_entry(db, ramesh, "credit", 150)
    assert get_balance_paise(db, ramesh.id) == 15000


def test_payment_decreases_outstanding(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 500)
    post_entry(db, ramesh, "payment", 200)
    assert get_balance_paise(db, ramesh.id) == 30000


def test_multiple_transactions_accumulate(db):
    ramesh = make_customer(db, "Ramesh")
    for rupees in (100, 250, 50):
        post_entry(db, ramesh, "credit", rupees)
    post_entry(db, ramesh, "payment", 150)
    assert get_balance_paise(db, ramesh.id) == 25000


def test_balances_are_derived_per_customer(db):
    ramesh = make_customer(db, "Ramesh")
    sunita = make_customer(db, "Sunita")
    post_entry(db, ramesh, "credit", 400)
    post_entry(db, sunita, "credit", 900)
    post_entry(db, sunita, "payment", 100)
    assert get_balance_paise(db, ramesh.id) == 40000
    assert get_balance_paise(db, sunita.id) == 80000


# ---------------------------------------------------------------------------
# Preview / confirmation safety
# ---------------------------------------------------------------------------


def test_preview_does_not_touch_the_ledger(db):
    make_customer(db, "Ramesh")
    response = handle_command(db, "Ramesh ko dedh sau rupaye ka udhaar likh do")
    assert response["kind"] == "proposal"
    assert count(db, Transaction) == 0
    assert count(db, PendingTransaction) == 1
    assert response["proposal"]["balance_before_text"] == "₹0"
    assert response["proposal"]["balance_after_text"] == "₹150"


def test_confirm_posts_exactly_one_transaction(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    result = confirm_pending(db, proposal["pending_id"])
    assert result["already_confirmed"] is False
    assert count(db, Transaction) == 1
    assert result["customer"]["balance_paise"] == 15000
    assert "Ab baaki ₹150" in result["message"] or "₹150" in result["message"]


def test_cancel_leaves_ledger_unchanged(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    result = cancel_pending(db, proposal["pending_id"])
    assert result["kind"] == "cancelled"
    assert count(db, Transaction) == 0
    assert get_balance_paise(db, ramesh.id) == 0
    pending = db.get(PendingTransaction, proposal["pending_id"])
    assert pending.status == "cancelled"


def test_cancel_is_idempotent(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    cancel_pending(db, proposal["pending_id"])
    again = cancel_pending(db, proposal["pending_id"])
    assert again["already"] is True
    assert count(db, Transaction) == 0


def test_duplicate_confirm_is_idempotent(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    first = confirm_pending(db, proposal["pending_id"])
    second = confirm_pending(db, proposal["pending_id"])
    assert second["already_confirmed"] is True
    assert second["transaction"]["id"] == first["transaction"]["id"]
    assert count(db, Transaction) == 1
    assert get_balance_paise(db, ramesh.id) == 15000


def test_cancelled_pending_cannot_be_confirmed(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    cancel_pending(db, proposal["pending_id"])
    with pytest.raises(ServiceError) as error:
        confirm_pending(db, proposal["pending_id"])
    assert error.value.code == "pending_cancelled"
    assert count(db, Transaction) == 0


def test_expired_pending_cannot_be_confirmed(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    pending = db.get(PendingTransaction, proposal["pending_id"])
    pending.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    with pytest.raises(ServiceError) as error:
        confirm_pending(db, proposal["pending_id"])
    assert error.value.code == "pending_expired"
    assert count(db, Transaction) == 0


def test_confirmed_transaction_cannot_be_cancelled(db):
    ramesh = make_customer(db, "Ramesh")
    proposal = create_pending_entry(db, ramesh, "credit", "150")
    confirm_pending(db, proposal["pending_id"])
    with pytest.raises(ServiceError) as error:
        cancel_pending(db, proposal["pending_id"])
    assert error.value.code == "already_confirmed"
    assert count(db, Transaction) == 1


def test_unknown_pending_returns_404(db):
    with pytest.raises(ServiceError) as error:
        confirm_pending(db, "does-not-exist")
    assert error.value.status_code == 404


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def test_transaction_stores_audit_fields(db):
    ramesh = make_customer(db, "Ramesh")
    transcript = "Ramesh ko dedh sau rupaye ka udhaar likh do"
    response = handle_command(db, transcript, source="voice")
    proposal = response["proposal"]
    confirm_pending(db, proposal["pending_id"])

    txn = db.scalars(select(Transaction)).one()
    assert txn.customer_id == ramesh.id
    assert txn.type == "credit"
    assert txn.amount_paise == 15000
    assert txn.transcript == transcript
    assert txn.source == "voice"
    assert txn.pending_id == proposal["pending_id"]
    assert txn.balance_after_paise == 15000
    assert txn.created_at is not None

    pending = db.get(PendingTransaction, proposal["pending_id"])
    assert pending.status == "confirmed"
    assert pending.confirmed_transaction_id == txn.id
    assert json.loads(pending.parser_json)["intent"] == "add_credit"


def test_invalid_pending_amounts_are_rejected(db):
    ramesh = make_customer(db, "Ramesh")
    from services import create_pending

    with pytest.raises(ServiceError) as zero:
        create_pending(db, ramesh, "credit", 0, "x", "text", {})
    assert zero.value.code == "invalid_amount"
    with pytest.raises(ServiceError) as negative:
        create_pending(db, ramesh, "credit", -500, "x", "text", {})
    assert negative.value.code == "invalid_amount"
    assert count(db, Transaction) == 0


# ---------------------------------------------------------------------------
# Overpayment protection
# ---------------------------------------------------------------------------


def test_payment_equal_to_balance_needs_no_ack(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 500)
    response = handle_command(db, "Ramesh ne 500 rupaye wapas kar diye")
    proposal = response["proposal"]
    assert proposal["requires_overpayment_ack"] is False
    result = confirm_pending(db, proposal["pending_id"])
    assert result["customer"]["balance_paise"] == 0


def test_overpayment_requires_explicit_acknowledgement(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 100)
    proposal = create_pending_entry(db, ramesh, "payment", "500")
    assert proposal["requires_overpayment_ack"] is True
    assert proposal["balance_after_paise"] == -40000

    with pytest.raises(ServiceError) as error:
        confirm_pending(db, proposal["pending_id"])
    assert error.value.code == "overpayment_ack_required"
    assert count(db, Transaction) == 1  # only the opening credit
    assert get_balance_paise(db, ramesh.id) == 10000

    result = confirm_pending(db, proposal["pending_id"], acknowledge_overpayment=True)
    assert result["customer"]["balance_paise"] == -40000
    assert count(db, Transaction) == 2


def test_overpayment_is_rechecked_when_balance_changed_after_preview(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 500)
    response = handle_command(db, "Ramesh ne 400 rupaye jama kiye")
    proposal = response["proposal"]
    assert proposal["requires_overpayment_ack"] is False

    # Another payment lands before the shopkeeper confirms the first preview.
    post_entry(db, ramesh, "payment", 200)
    with pytest.raises(ServiceError) as error:
        confirm_pending(db, proposal["pending_id"])
    assert error.value.code == "overpayment_ack_required"

    pending = db.get(PendingTransaction, proposal["pending_id"])
    assert pending.status == "pending"
    assert pending.requires_overpayment_ack is True
    assert get_balance_paise(db, ramesh.id) == 30000

    confirm_pending(db, proposal["pending_id"], acknowledge_overpayment=True)
    assert get_balance_paise(db, ramesh.id) == -10000


# ---------------------------------------------------------------------------
# Customer resolution
# ---------------------------------------------------------------------------


def test_unknown_customer_never_creates_a_pending_row(db):
    response = handle_command(db, "Ramesh ko 500 rupaye ka udhaar likh do")
    assert response["kind"] == "clarification"
    assert "customer" in response["clarification"]["needs"]
    assert count(db, PendingTransaction) == 0
    assert count(db, Transaction) == 0


def test_fuzzy_name_offers_choices_instead_of_guessing(db):
    make_customer(db, "Ramesh")
    response = handle_command(db, "Ramessh ko 500 rupaye ka udhaar likh do")
    assert response["kind"] == "clarification"
    names = [customer["name"] for customer in response["clarification"]["customers"]]
    assert "Ramesh" in names
    assert count(db, PendingTransaction) == 0


def test_customer_override_resolves_ambiguity(db):
    make_customer(db, "Ramesh")
    sunita = make_customer(db, "Sunita")
    response = handle_command(
        db, "Ramessh ko 500 rupaye ka udhaar likh do", customer_id=sunita.id
    )
    assert response["kind"] == "proposal"
    assert response["proposal"]["customer"]["id"] == sunita.id


def test_devanagari_name_matches_latin_customer(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 250)
    response = handle_command(db, "रमेश का कितना उधार बाकी है")
    assert response["kind"] == "answer", response
    assert response["answer"]["customer"]["id"] == ramesh.id
    assert response["answer"]["balance_paise"] == 25000


def test_balance_query_without_name_asks_for_customer(db):
    make_customer(db, "Ramesh")
    response = handle_command(db, "kitna udhaar baaki hai")
    assert response["kind"] == "clarification"
    assert "customer" in response["clarification"]["needs"]


def test_balance_query_reports_advance(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 100)
    post_entry(db, ramesh, "payment", 300, )
    response = handle_command(db, "Ramesh ka kitna udhaar baaki hai")
    assert response["answer"]["balance_paise"] == -20000
    assert "advance" in response["message"].lower()


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


def insert_direct_transaction(db, customer, txn_type: str, rupees: int, when):
    from money import to_paise

    txn = Transaction(
        customer_id=customer.id,
        type=txn_type,
        amount_paise=to_paise(rupees),
        created_at=when,
        transcript="direct test row",
        source="text",
        balance_after_paise=to_paise(rupees) * (1 if txn_type == "credit" else -1),
    )
    db.add(txn)
    db.commit()
    return txn


def test_daily_summary_counts_today_only_in_ist(db):
    ramesh = make_customer(db, "Ramesh")
    today = today_ist()
    start, _ = ist_day_bounds(today)

    insert_direct_transaction(db, ramesh, "credit", 500, start - timedelta(minutes=10))  # 23:50 IST yesterday
    insert_direct_transaction(db, ramesh, "credit", 150, start + timedelta(minutes=10))   # 00:10 IST today
    insert_direct_transaction(db, ramesh, "payment", 50, start + timedelta(hours=9))      # 09:00 IST today

    summary = daily_summary(db, today)
    assert summary["credit_paise"] == 15000
    assert summary["payment_paise"] == 5000
    assert summary["net_paise"] == 10000
    assert summary["transaction_count"] == 2
    assert summary["credit_count"] == 1
    assert summary["payment_count"] == 1


def test_daily_summary_on_empty_day_is_zero():
    from database import SessionLocal

    with SessionLocal() as session:
        summary = daily_summary(session, today_ist() - timedelta(days=30))
        assert summary["credit_paise"] == 0
        assert summary["payment_paise"] == 0
        assert summary["transaction_count"] == 0
        assert "koi transaction nahi" in summary["reply_text"]


def test_daily_summary_reminders_are_suggestions_only(db):
    ramesh = make_customer(db, "Ramesh")
    post_entry(db, ramesh, "credit", 500)
    summary = daily_summary(db)
    assert summary["reminders"]
    assert "Ramesh" in summary["reminders"][0]
    assert "yaad" in summary["reminders"][0].lower()


def test_top_debtors_ordering_excludes_settled_customers(db):
    ramesh = make_customer(db, "Ramesh")
    sunita = make_customer(db, "Sunita")
    mohan = make_customer(db, "Mohan")
    post_entry(db, ramesh, "credit", 600)
    post_entry(db, sunita, "credit", 1500)
    post_entry(db, mohan, "credit", 200)
    post_entry(db, mohan, "payment", 200)

    ranked = top_debtors(db)
    assert [row["name"] for row in ranked] == ["Sunita", "Ramesh"]
    assert ranked[0]["balance_paise"] == 150000


def test_dashboard_totals_are_derived_from_transactions(db):
    ramesh = make_customer(db, "Ramesh")
    sunita = make_customer(db, "Sunita")
    post_entry(db, ramesh, "credit", 500)
    post_entry(db, sunita, "credit", 300)
    post_entry(db, sunita, "payment", 100)

    data = dashboard(db)
    assert data["total_outstanding_paise"] == 70000
    assert data["total_outstanding_text"] == "₹700"
    assert data["customer_count"] == 2
    assert data["transaction_count"] == 3
    assert data["today_credit_text"] == "₹800"
    assert data["today_payment_text"] == "₹100"
    assert data["today_net_paise"] == 70000


# ---------------------------------------------------------------------------
# Manual correction path
# ---------------------------------------------------------------------------


def test_manual_proposal_still_requires_confirmation(db):
    ramesh = make_customer(db, "Ramesh")
    response = manual_proposal(db, ramesh.id, "credit", Decimal("250"))
    assert response["kind"] == "proposal"
    assert response["proposal"]["amount_text"] == "₹250"
    assert count(db, Transaction) == 0

    result = confirm_pending(db, response["proposal"]["pending_id"])
    assert result["already_confirmed"] is False
    assert get_balance_paise(db, ramesh.id) == 25000


def test_manual_proposal_rejects_unknown_customer(db):
    with pytest.raises(ServiceError) as error:
        manual_proposal(db, 999, "credit", Decimal("100"))
    assert error.value.code == "unknown_customer"


def test_manual_proposal_rejects_bad_type(db):
    ramesh = make_customer(db, "Ramesh")
    with pytest.raises(ServiceError) as error:
        manual_proposal(db, ramesh.id, "loan", Decimal("100"))
    assert error.value.code == "invalid_type"
