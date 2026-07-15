"""
schemas/expense.py
------------------
Pydantic v2 schemas for the Expense domain.

This is the most complex schema file — it covers all four expense types
(HOTEL, MEAL, TAXI, FLIGHT), their nested detail sub-objects, and the
bulk submit request body.

Request hierarchy for POST /api/v4/expense-reports/{id}/expenses:

  ExpensesSubmitRequest
    └── expenses: list[ExpenseInput]
          ├── itemization: list[HotelItemizationInput]  (HOTEL only)
          ├── airfare_detail: AirfareDetailInput         (FLIGHT only)
          ├── taxi_detail: TaxiDetailInput               (TAXI only)
          └── meal_detail: MealDetailInput               (MEAL only)

All field names use camelCase aliases to match SAP Concur v4 conventions.
The `ocrConfidence` field is optional — passed through from Layer 2 and
used by OcrConfidenceValidator in the policy engine.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common import (
    ExpenseStatus,
    ExpenseType,
    MealType,
    PaymentType,
    TravelClass,
    ValidationWarning,
)


# ------------------------------------------------------------------ #
# Hotel itemization                                                    #
# ------------------------------------------------------------------ #

class HotelItemizationInput(BaseModel):
    """
    One night of a hotel stay.
    room_rate is the per-night charge before taxes — validated against
    NIGHTLY_LIMIT by HotelNightlyLimitValidator.
    """
    model_config = ConfigDict(populate_by_name=True)

    night_date: date = Field(
        ...,
        alias="nightDate",
        description="Calendar date of this overnight stay",
        examples=["2026-07-21"],
    )
    room_rate: float = Field(
        ...,
        alias="roomRate",
        description="Nightly room charge before taxes (policy-validated)",
        examples=[5500.0],
    )
    taxes: float = Field(default=0.0, description="Tax amount for this night", examples=[990.0])
    incidentals: float = Field(default=0.0, description="Incidental charges", examples=[150.0])


class HotelItemizationResponse(HotelItemizationInput):
    """Hotel itemization line as stored and returned from the DB."""
    line_id: str = Field(..., alias="lineId")
    line_total: float = Field(..., alias="lineTotal")


# ------------------------------------------------------------------ #
# Type-specific detail sub-objects                                     #
# ------------------------------------------------------------------ #

class AirfareDetailInput(BaseModel):
    """Required for FLIGHT expenses. travel_class is policy-validated."""
    model_config = ConfigDict(populate_by_name=True)

    origin: str = Field(..., description="Departure airport/city", examples=["Bengaluru"])
    destination: str = Field(..., description="Arrival airport/city", examples=["Delhi"])
    flight_number: Optional[str] = Field(default=None, alias="flightNumber", examples=["6E-204"])
    travel_class: TravelClass = Field(
        ...,
        alias="travelClass",
        description="Cabin class — ECONOMY or BUSINESS",
    )
    ticket_number: Optional[str] = Field(default=None, alias="ticketNumber")


class TaxiDetailInput(BaseModel):
    """Optional detail for TAXI expenses."""
    model_config = ConfigDict(populate_by_name=True)

    from_location: str = Field(
        ...,
        alias="fromLocation",
        description="Pickup location",
        examples=["Kempegowda International Airport"],
    )
    to_location: str = Field(
        ...,
        alias="toLocation",
        description="Drop-off location",
        examples=["Marriott, Bengaluru"],
    )
    distance_km: Optional[float] = Field(
        default=None,
        alias="distanceKm",
        description="Trip distance in kilometres (optional)",
    )


class MealDetailInput(BaseModel):
    """Optional detail for MEAL expenses."""
    model_config = ConfigDict(populate_by_name=True)

    meal_type: MealType = Field(
        default=MealType.MEAL,
        alias="mealType",
    )
    attendees: int = Field(
        default=1,
        description="Number of people covered by this meal expense",
        ge=1,
    )


# ------------------------------------------------------------------ #
# Core expense input                                                   #
# ------------------------------------------------------------------ #

class ExpenseInput(BaseModel):
    """
    A single expense line within a bulk submit request.

    Validation rules enforced at this schema level (Pydantic layer):
    - amount must be > 0
    - currency must be a non-empty string
    - transactionDate must be a valid ISO date

    Pre-flight validation (Step 3) performs deeper business checks
    (allowed currencies, expense types, itemization presence) in the
    service layer after Pydantic has accepted the model.
    """
    model_config = ConfigDict(populate_by_name=True)

    expense_type: ExpenseType = Field(..., alias="expenseType")
    vendor: str = Field(
        ...,
        min_length=1,
        description="Vendor name as extracted by Layer 2 OCR",
        examples=["Marriott"],
    )
    amount: float = Field(
        ...,
        gt=0,
        description="Total expense amount",
        examples=[18000.0],
    )
    currency: str = Field(
        ...,
        min_length=1,
        description="ISO 4217 currency code",
        examples=["INR"],
    )
    transaction_date: date = Field(
        ...,
        alias="transactionDate",
        description="Date of the transaction (ISO 8601)",
        examples=["2026-07-21"],
    )
    city: str = Field(
        ...,
        description="City where the expense was incurred",
        examples=["Bengaluru"],
    )
    payment_type: PaymentType = Field(
        ...,
        alias="paymentType",
    )
    receipt_id: Optional[str] = Field(
        default=None,
        alias="receiptId",
        description="ID of the receipt registered via POST /receipts/register",
    )
    notes: Optional[str] = Field(default=None)
    ocr_confidence: Optional[float] = Field(
        default=None,
        alias="ocrConfidence",
        description="OCR confidence score from Layer 2 (0.0–1.0). Used by OcrConfidenceValidator.",
        ge=0.0,
        le=1.0,
    )

    # Type-specific detail sub-objects
    itemization: Optional[List[HotelItemizationInput]] = Field(
        default=None,
        description="Required for HOTEL expenses. One entry per night.",
    )
    airfare_detail: Optional[AirfareDetailInput] = Field(
        default=None,
        alias="airfareDetail",
        description="Required for FLIGHT expenses.",
    )
    taxi_detail: Optional[TaxiDetailInput] = Field(
        default=None,
        alias="taxiDetail",
    )
    meal_detail: Optional[MealDetailInput] = Field(
        default=None,
        alias="mealDetail",
    )

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        """Normalise currency to uppercase at the Pydantic layer."""
        return v.upper()


# ------------------------------------------------------------------ #
# Bulk submit request                                                  #
# ------------------------------------------------------------------ #

class ExpensesSubmitRequest(BaseModel):
    """
    Request body for POST /api/v4/expense-reports/{reportId}/expenses.
    Contains the employee ID (for ownership verification) and the list
    of expenses extracted by Layer 2.
    """
    model_config = ConfigDict(populate_by_name=True)

    employee_id: str = Field(
        ...,
        alias="employeeId",
        description="Must match the owner of the report",
        examples=["EMP001"],
    )
    expenses: list[ExpenseInput] = Field(
        ...,
        min_length=1,
        description="At least one expense is required per submission",
    )


# ------------------------------------------------------------------ #
# Expense response (GET /expense-reports/{id})                        #
# ------------------------------------------------------------------ #

class ExpenseResponse(BaseModel):
    """
    A single expense line as returned in GET /expense-reports/{id}.
    Provides the full picture of a persisted expense including its
    processing status and matched card transaction.
    """
    model_config = ConfigDict(populate_by_name=True)

    expense_id: str = Field(..., alias="expenseId")
    expense_type: ExpenseType = Field(..., alias="expenseType")
    vendor: str
    amount: float
    currency: str
    transaction_date: date = Field(..., alias="transactionDate")
    city: str
    payment_type: PaymentType = Field(..., alias="paymentType")
    status: ExpenseStatus
    card_transaction_id: Optional[str] = Field(default=None, alias="cardTransactionId")
    receipt_id: Optional[str] = Field(default=None, alias="receiptId")
    notes: Optional[str] = None
    created_at: datetime = Field(..., alias="createdAt")

    # Nested detail (populated if present)
    itemization: Optional[List[HotelItemizationResponse]] = None
    airfare_detail: Optional[AirfareDetailInput] = Field(default=None, alias="airfareDetail")
    taxi_detail: Optional[TaxiDetailInput] = Field(default=None, alias="taxiDetail")
    meal_detail: Optional[MealDetailInput] = Field(default=None, alias="mealDetail")
    warnings: list[ValidationWarning] = Field(default_factory=list)
