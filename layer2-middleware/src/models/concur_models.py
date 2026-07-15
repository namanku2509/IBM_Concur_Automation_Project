"""
Concur models — Pydantic v2

These mirror the exact JSON shapes that Layer 3 expects to receive
and returns in responses. Aligned with concur-stub actual API (2026-01).

When Layer 3 finalises its schema, update these models to match —
all service code stays unchanged.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Outbound payloads (Layer 2 → Layer 3) ────────────────────────────────────

class HotelItemizationInput(BaseModel):
    """One night of a hotel stay for ExpenseInput.itemization[]."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    night_date: str = Field(..., alias="nightDate")       # YYYY-MM-DD
    room_rate: float = Field(..., alias="roomRate")
    taxes: float = Field(default=0.0)
    incidentals: float = Field(default=0.0)


class AirfareDetailInput(BaseModel):
    """Required for FLIGHT expenses."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    origin: Optional[str] = None
    destination: Optional[str] = None
    flight_number: Optional[str] = Field(default=None, alias="flightNumber")
    travel_class: str = Field(default="ECONOMY", alias="travelClass")
    ticket_number: Optional[str] = Field(default=None, alias="ticketNumber")


class TaxiDetailInput(BaseModel):
    """Optional detail for TAXI expenses."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    from_location: Optional[str] = Field(default=None, alias="fromLocation")
    to_location: Optional[str] = Field(default=None, alias="toLocation")
    distance_km: Optional[float] = Field(default=None, alias="distanceKm")


class MealDetailInput(BaseModel):
    """Optional detail for MEAL expenses."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    meal_type: str = Field(default="MEAL", alias="mealType")
    attendees: int = Field(default=1)


class ExpenseInput(BaseModel):
    """
    A single expense line for POST /api/v4/expense-reports/{report_id}/expenses.
    Uses camelCase aliases to match SAP Concur v4 / Layer 3 convention.
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # Layer 3 ExpenseType enum: HOTEL | MEAL | TAXI | FLIGHT
    expense_type: Literal["HOTEL", "MEAL", "TAXI", "FLIGHT"] = Field(..., alias="expenseType")
    vendor: str
    amount: float
    currency: str = Field(default="INR")
    transaction_date: str = Field(..., alias="transactionDate")   # YYYY-MM-DD
    city: str
    payment_type: Literal["CORPORATE_CARD", "PERSONAL_CASH", "CORPORATE_CASH"] = Field(
        default="PERSONAL_CASH", alias="paymentType"
    )
    receipt_id: Optional[str] = Field(default=None, alias="receiptId")
    notes: Optional[str] = None
    ocr_confidence: Optional[float] = Field(default=None, alias="ocrConfidence")

    # Type-specific detail sub-objects
    itemization: Optional[list[HotelItemizationInput]] = None
    airfare_detail: Optional[AirfareDetailInput] = Field(default=None, alias="airfareDetail")
    taxi_detail: Optional[TaxiDetailInput] = Field(default=None, alias="taxiDetail")
    meal_detail: Optional[MealDetailInput] = Field(default=None, alias="mealDetail")


class ExpensesSubmitRequest(BaseModel):
    """
    Body for POST /api/v4/expense-reports/{report_id}/expenses.
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    employee_id: str = Field(..., alias="employeeId")
    expenses: list[ExpenseInput]


# ── Receipt registration ──────────────────────────────────────────────────────

class ReceiptRegisterRequest(BaseModel):
    """
    Body for POST /api/v4/receipts/register.
    Layer 2 submits this after OCR to get a receiptId.
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    employee_id: str = Field(..., alias="employeeId")
    receipt_hash: str = Field(..., alias="receiptHash")
    file_name: Optional[str] = Field(default=None, alias="fileName")
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    ocr_confidence: Optional[float] = Field(default=None, alias="ocrConfidence")


class ReceiptRegisterResponse(BaseModel):
    """Response from POST /api/v4/receipts/register."""
    model_config = ConfigDict(extra="ignore")

    receipt_id: str
    employee_id: str
    registered_at: Any = None


# ── Inbound data from Layer 3 ─────────────────────────────────────────────────

class AvailableTransaction(BaseModel):
    """
    One corporate card transaction returned by:
    GET /api/v4/card-transactions?employeeId=<id>
    Stored with snake_case internally (normalised in concur_client.py).
    """
    model_config = ConfigDict(extra="ignore")

    txn_id: str
    employee_id: str
    vendor: Optional[str] = None
    amount: float
    currency: str = "INR"
    transaction_date: Optional[str] = None   # YYYY-MM-DD
    status: str = "AVAILABLE"
    matched_expense_id: Optional[str] = None


class SubmitExpensesResponse(BaseModel):
    """
    Response from POST /api/v4/expense-reports/{id}/expenses.
    Shape: { reportId, status, warnings[], processedExpenses[], summary{} }
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    report_id: str = Field(..., alias="reportId")
    status: str
    warnings: list[Any] = Field(default_factory=list)
    processed_expenses: list[Any] = Field(default_factory=list, alias="processedExpenses")
    summary: Optional[Any] = None
