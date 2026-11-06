"""Pydantic request/response contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CommandRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=600, description="Hindi/Hinglish instruction")
    source: Literal["voice", "text"] = "text"
    customer_id: int | None = Field(
        default=None,
        description="Optional explicit customer choice when the name was ambiguous",
    )


class ConfirmRequest(BaseModel):
    acknowledge_overpayment: bool = Field(
        default=False,
        description="Must be true when a payment exceeds the current outstanding balance",
    )


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=600)


class ManualProposalRequest(BaseModel):
    "Correct-details fallback: the shopkeeper fixes customer/type/amount by hand."

    customer_id: int
    type: Literal["credit", "payment"]
    amount_rupees: Decimal = Field(..., gt=0, le=Decimal("10000000"))
    transcript: str | None = Field(default=None, max_length=600)


class SttResponse(BaseModel):
    transcript: str
    provider: str = "gnani-prisma"
    language: str
    request_id: str | None = None
    model: str | None = None
    audio: dict


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, description="Customer ka naam")


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    balance_paise: int
    balance_text: str
    is_sample: bool
