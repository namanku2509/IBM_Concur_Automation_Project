"""
Pipeline models — Pydantic v2

Shapes for the /pipeline/run request and response.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Type-specific detail blocks (mirrored from receipt_models for the response) ─

class HotelDetailResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    check_in_date: Optional[str] = None       # YYYY-MM-DD
    check_out_date: Optional[str] = None      # YYYY-MM-DD
    num_nights: Optional[int] = None
    nightly_rate: Optional[float] = None
    tax_amount: Optional[float] = None


class AirfareDetailResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    origin: Optional[str] = None
    destination: Optional[str] = None
    airline: Optional[str] = None
    ticket_number: Optional[str] = None
    travel_class: Optional[str] = None
    passenger_name: Optional[str] = None


class TaxiDetailResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    distance_km: Optional[float] = None


class MealDetailResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    meal_type: Optional[str] = None
    num_attendees: Optional[int] = None
    business_justification: Optional[str] = None


class RegistrationDetailResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_name: Optional[str] = None
    event_date: Optional[str] = None          # YYYY-MM-DD
    registration_id: Optional[str] = None
    organiser: Optional[str] = None


class ReceiptResult(BaseModel):
    """Result for a single PDF receipt processed through the full pipeline."""
    model_config = ConfigDict(extra="ignore")

    filename: str = Field(description="Original PDF filename")
    status: Literal["success", "error"] = "success"

    # ── Core expense fields ───────────────────────────────────────────────────
    expense_type: Optional[Literal["HOTEL", "TAXI", "FLIGHT", "MEALS", "REGISTRATION"]] = None
    vendor: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    transaction_date: Optional[str] = None   # YYYY-MM-DD
    city: Optional[str] = None
    payment_type: Optional[str] = None

    # ── Type-specific detail sub-objects (one will be populated per receipt) ──
    hotel_detail: Optional[HotelDetailResult] = Field(
        default=None, description="Populated only for HOTEL expenses"
    )
    airfare_detail: Optional[AirfareDetailResult] = Field(
        default=None, description="Populated only for FLIGHT expenses"
    )
    taxi_detail: Optional[TaxiDetailResult] = Field(
        default=None, description="Populated only for TAXI expenses"
    )
    meal_detail: Optional[MealDetailResult] = Field(
        default=None, description="Populated only for MEALS expenses"
    )
    registration_detail: Optional[RegistrationDetailResult] = Field(
        default=None, description="Populated only for REGISTRATION expenses"
    )

    # ── Matching result ───────────────────────────────────────────────────────
    matched_txn_id: Optional[str] = Field(
        default=None,
        description="Corporate card transaction ID that was matched, or null"
    )
    match_confidence: Optional[float] = Field(
        default=None,
        description="Composite match score 0–1, or null if no match attempted"
    )

    # ── Layer 3 response ──────────────────────────────────────────────────────
    expense_id: Optional[str] = Field(
        default=None,
        description="Expense ID assigned by Layer 3 after submission"
    )
    warnings: list[Any] = Field(
        default_factory=list,
        description="Policy warnings passed through from Layer 3"
    )

    # ── OCR metadata ──────────────────────────────────────────────────────────
    ocr_engine: Optional[Literal["docling", "pytesseract-fallback"]] = None
    page_count: Optional[int] = None
    file_hash: Optional[str] = Field(
        default=None, description="SHA-256 of the PDF — used for duplicate detection"
    )

    # ── Error info ────────────────────────────────────────────────────────────
    error_message: Optional[str] = None

    # ── Dry run flag ──────────────────────────────────────────────────────────
    dry_run: bool = Field(
        default=False,
        description="True when Layer 3 submission was skipped (DRY_RUN=true)"
    )


class PipelineSummary(BaseModel):
    """Aggregate summary across all receipts in the batch."""
    model_config = ConfigDict(extra="ignore")

    total_amount: float = 0.0
    currency: str = "INR"
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count of expenses per type: {HOTEL: 1, TAXI: 2, ...}"
    )


class PipelineResult(BaseModel):
    """Full response for POST /pipeline/run."""
    model_config = ConfigDict(extra="ignore")

    report_id: str
    employee_id: str
    processed: int = Field(description="Total number of PDF files received")
    matched: int = Field(description="Number of receipts matched to a card transaction")
    unmatched: int = Field(description="Receipts with no card transaction match")
    errors: int = Field(default=0, description="Receipts that failed processing")
    results: list[ReceiptResult]
    summary: PipelineSummary
