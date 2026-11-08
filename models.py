"""SQLAlchemy models.

Balances are never stored on the customer row. They are always derived from the
immutable transaction log, so an outstanding balance cannot be overwritten.
Every transaction additionally stores an audit snapshot of the balance after it
was posted.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def new_id() -> str:
    return uuid.uuid4().hex


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('credit', 'payment')", name="ck_transaction_type"),
        CheckConstraint("amount_paise > 0", name="ck_transaction_amount_positive"),
        Index("ix_transactions_customer_created", "customer_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="text")
    # One confirmed pending action can create at most one transaction.
    pending_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    balance_after_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    customer: Mapped[Customer] = relationship(back_populates="transactions")


class PendingTransaction(Base):
    """A previewed action. Never part of the ledger until explicitly confirmed."""

    __tablename__ = "pending_transactions"
    __table_args__ = (
        CheckConstraint("type IN ('credit', 'payment')", name="ck_pending_type"),
        CheckConstraint("amount_paise > 0", name="ck_pending_amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'expired')",
            name="ck_pending_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="text")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    balance_before_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_overpayment_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parser_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
