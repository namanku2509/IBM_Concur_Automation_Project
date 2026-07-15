"""
schemas/card_transaction.py
----------------------------
Pydantic v2 schemas for the CorporateCardTransaction domain.

GET  /api/v4/card-transactions?employeeId=EMP001  → list[CardTransactionResponse]
POST /admin/card-transactions                     → CardTransactionCreate (test harness)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import CardTxnStatus


class CardTransactionResponse(BaseModel):
    """A corporate card transaction as returned to Layer 2 or the admin dashboard."""
    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        alias="transactionId",
        description="Unique card transaction ID",
        examples=["CCT001"],
    )
    employee_id: str = Field(..., alias="employeeId")
    vendor: str = Field(..., examples=["Marriott"])
    amount: float = Field(..., examples=[18000.0])
    currency: str = Field(..., examples=["INR"])
    transaction_date: date = Field(..., alias="transactionDate")
    card_last_four: str = Field(..., alias="cardLastFour", examples=["4242"])
    status: CardTxnStatus
    matched_expense_id: Optional[str] = Field(default=None, alias="matchedExpenseId")
    created_at: datetime = Field(..., alias="createdAt")


class CardTransactionCreate(BaseModel):
    """
    Request body for POST /admin/card-transactions.
    Used by the test harness to inject card transactions without
    restarting the server or modifying seed data.
    """
    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        alias="transactionId",
        description="Must be unique across all card transactions",
        examples=["CCT099"],
    )
    employee_id: str = Field(..., alias="employeeId", examples=["EMP001"])
    vendor: str = Field(..., examples=["Marriott"])
    amount: float = Field(..., gt=0, examples=[5000.0])
    currency: str = Field(..., min_length=1, examples=["INR"])
    transaction_date: date = Field(..., alias="transactionDate")
    card_last_four: str = Field(..., alias="cardLastFour", min_length=4, max_length=4, examples=["4242"])


class CardTransactionListResponse(BaseModel):
    """Response envelope for GET /api/v4/card-transactions."""
    model_config = ConfigDict(populate_by_name=True)

    employee_id: str = Field(..., alias="employeeId")
    transactions: list[CardTransactionResponse]
    total: int = Field(..., description="Total number of transactions returned")
