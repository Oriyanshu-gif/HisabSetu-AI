"""Synthetic demo data.

Eight fictional customers, no phone numbers / IDs / real people. Every row is
flagged ``is_sample=True`` and the UI labels it as sample data. Amounts are
posted through the same ledger rules as real entries so the arithmetic is
consistently derived from the transactions.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import Customer, Transaction
from money import to_paise
from parser import normalize_name
from services import ist_day_bounds, today_ist, utcnow

SAMPLE_CUSTOMERS: list[tuple[str, list[tuple[str, int, int, str]]]] = [
    # name, [(type, rupees, days_ago, transcript)]
    (
        "Suresh",
        [
            ("credit", 2500, 12, "Suresh ko do hazaar paanch sau rupaye ka udhaar likh do"),
            ("payment", 500, 6, "Suresh ne paanch sau rupaye wapas kar diye"),
        ],
    ),
    (
        "Mohan",
        [
            ("credit", 1200, 5, "Mohan ko bara sau rupaye ka udhaar likh do"),
        ],
    ),
    (
        "Kavita",
        [
            ("credit", 800, 4, "Kavita ko aath sau rupaye ka udhaar likh do"),
            ("payment", 300, 2, "Kavita ne teen sau rupaye jama kiye"),
        ],
    ),
    (
        "Ramesh",
        [
            ("credit", 500, 3, "Ramesh ko paanch sau rupaye ka udhaar likh do"),
            ("payment", 200, 2, "Ramesh ne do sau rupaye wapas kar diye"),
            ("credit", 150, 0, "Ramesh ko dedh sau rupaye ka udhaar likh do"),
        ],
    ),
    (
        "Sunita",
        [
            ("credit", 200, 1, "Sunita ko do sau rupaye ka udhaar likh do"),
            ("payment", 50, 0, "Sunita ne pachaas rupaye wapas kar diye"),
        ],
    ),
    (
        "Priya",
        [
            ("credit", 300, 1, "Priya ko teen sau rupaye ka udhaar likh do"),
        ],
    ),
    (
        "Anil",
        [
            ("credit", 450, 7, "Anil ko chaar sau pachaas rupaye ka udhaar likh do"),
            ("payment", 450, 3, "Anil ne poore chaar sau pachaas rupaye jama kiye"),
        ],
    ),
    ("Meena", []),
]


def _at_local_day(days_ago: int, hour: int = 11) -> datetime:
    day = today_ist() - timedelta(days=days_ago)
    start, _ = ist_day_bounds(day)
    # start is UTC; shift a few hours into the IST working day
    return start + timedelta(hours=hour)


def seed_sample_data(db: Session, force: bool = False) -> bool:
    """Insert sample data only when the customers table is empty."""
    existing = db.scalar(select(func.count(Customer.id))) or 0
    if existing and not force:
        return False

    now = utcnow()
    for name, entries in SAMPLE_CUSTOMERS:
        customer = Customer(
            name=name,
            name_normalized=normalize_name(name),
            is_sample=True,
            created_at=now,
        )
        db.add(customer)
        db.flush()

        balance = 0
        for txn_type, rupees, days_ago, transcript in entries:
            amount = to_paise(rupees)
            delta = amount if txn_type == "credit" else -amount
            balance += delta
            db.add(
                Transaction(
                    customer_id=customer.id,
                    type=txn_type,
                    amount_paise=amount,
                    created_at=_at_local_day(days_ago),
                    transcript=transcript,
                    source="voice",
                    balance_after_paise=balance,
                    is_sample=True,
                )
            )
    db.commit()
    return True
