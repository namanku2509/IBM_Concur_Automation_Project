"""
Receipt models — Pydantic v2

Covers OCR output, type-specific detail blocks, and the unified
ExtractedExpense that flows through the whole pipeline.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── OCR stage output ─────────────────────────────────────────────────────────

class OcrResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_text: str = Field(description="Full text extracted from the PDF receipt")
    engine_used: Literal["docling", "pytesseract-fallback"] = Field(
        description="Which OCR engine produced this result"
    )
    file_hash: str = Field(
        description="SHA-256 of the raw PDF bytes — used for duplicate detection"
    )
    page_count: int = Field(default=1, description="Number of PDF pages processed")


# ── Categorisation stage output ───────────────────────────────────────────────

class CategorisationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expense_type: Literal["HOTEL", "TAXI", "FLIGHT", "MEALS", "REGISTRATION"] = Field(
        description="Classified expense type"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Model confidence score 0–1"
    )
    reasoning: Optional[str] = Field(
        default=None, description="LLM's brief reasoning (for debugging)"
    )


# ── Type-specific detail blocks ───────────────────────────────────────────────

class HotelDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    num_nights: Optional[int] = None
    nightly_rate: Optional[float] = None
    tax_amount: Optional[float] = Field(default=0.0)


class AirfareDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    origin: Optional[str] = None
    destination: Optional[str] = None
    airline: Optional[str] = None
    ticket_number: Optional[str] = None
    travel_class: Optional[str] = None
    passenger_name: Optional[str] = None


class TaxiDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    from_location: Optional[str] = None
    to_location: Optional[str] = None
    distance_km: Optional[float] = None


class MealDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meal_type: Optional[str] = None          # breakfast / lunch / dinner / snack
    num_attendees: Optional[int] = Field(default=1)
    business_justification: Optional[str] = None


class RegistrationDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_name: Optional[str] = None         # Conference, training, or event name
    event_date: Optional[date] = None        # Date of the event
    registration_id: Optional[str] = None   # Registration or booking ID
    organiser: Optional[str] = None         # Organising body / institution


# ── Unified extracted expense (output of extraction stage) ───────────────────

class ExtractedExpense(BaseModel):
    """
    Unified structure produced after OCR → Categorisation → Extraction.
    Carries all fields needed to populate the Layer 3 EXPENSES table
    plus the relevant type-specific detail table.
    """
    model_config = ConfigDict(extra="ignore")

    # Core EXPENSES fields
    expense_type: Literal["HOTEL", "TAXI", "FLIGHT", "MEALS", "REGISTRATION"]
    vendor: Optional[str] = None
    amount: float = Field(description="Total amount — never null")
    currency: str = Field(default="INR", description="3-letter ISO currency code")
    transaction_date: Optional[date] = None
    city: Optional[str] = None

    # Populated after matching stage
    payment_type: Literal["CORPORATE_CARD", "OUT_OF_POCKET"] = "OUT_OF_POCKET"

    # OCR provenance
    ocr_engine: Literal["docling", "pytesseract-fallback"] = "docling"  # noqa: E501
    file_hash: str = Field(description="SHA-256 of raw PDF — for duplicate detection")
    ocr_raw_text: str = Field(description="Raw OCR text passed to Granite")

    # Type-specific detail — only one will be populated per receipt
    hotel_detail: Optional[HotelDetail] = None
    airfare_detail: Optional[AirfareDetail] = None
    taxi_detail: Optional[TaxiDetail] = None
    meal_detail: Optional[MealDetail] = None
    registration_detail: Optional[RegistrationDetail] = None
