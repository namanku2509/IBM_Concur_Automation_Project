"""
Schema mapper.

Translates an ExtractedExpense (internal AI pipeline model) into the exact
JSON payload shapes that Layer 3 expects.

This is the only file that knows the mapping between pipeline internals
and the Layer 3 API contract. If Layer 3 changes its field names,
update this file only.

Key mappings (Layer 2 internal → Layer 3 ExpenseInput):
  MEALS        → MEAL            (Layer 3 enum does not have MEALS)
  hotel_detail → itemization[]   (Layer 3 uses per-night itemization, not a summary)
  CORPORATE_CARD / OUT_OF_POCKET are accepted; OUT_OF_POCKET maps to PERSONAL_CASH
"""

from __future__ import annotations

from src.models.concur_models import (
    AirfareDetailInput,
    ExpenseInput,
    HotelItemizationInput,
    MealDetailInput,
    ReceiptRegisterRequest,
    TaxiDetailInput,
)
from src.models.receipt_models import ExtractedExpense
from src.services.matching_service import MatchResult


def build_expense_input(
    extracted: ExtractedExpense,
    match_result: MatchResult,
    receipt_id: str | None = None,
    employee_id: str = "",
) -> ExpenseInput:
    """
    Build the JSON body for:
      POST /api/v4/expense-reports/{report_id}/expenses (inside expenses[])

    Populates:
      - Core fields from ExtractedExpense
      - payment_type from match_result (CORPORATE_CARD if matched, else PERSONAL_CASH)
      - The correct type-specific detail sub-object
      - receipt_id if one was registered with Layer 3
    """
    # CORPORATE_CARD if matched to a card transaction; otherwise PERSONAL_CASH
    payment_type = "CORPORATE_CARD" if match_result.txn_id else "PERSONAL_CASH"

    # Format date as string for JSON transport
    transaction_date_str = (
        extracted.transaction_date.isoformat()
        if extracted.transaction_date else ""
    )

    # Map MEALS → MEAL for Layer 3 enum compliance
    raw_type = extracted.expense_type
    expense_type = "MEAL" if raw_type == "MEALS" else raw_type

    # Only the four types Layer 3 accepts
    if expense_type not in ("HOTEL", "MEAL", "TAXI", "FLIGHT"):
        expense_type = "TAXI"   # safest fallback

    # Build type-specific detail sub-object
    itemization = None
    airfare_detail = None
    taxi_detail = None
    meal_detail = None

    if expense_type == "HOTEL" and extracted.hotel_detail:
        hd = extracted.hotel_detail
        nights = hd.num_nights or 1
        rate   = hd.nightly_rate or (extracted.amount / nights)
        taxes  = hd.tax_amount   or 0.0
        check_in = (
            hd.check_in_date.isoformat() if hd.check_in_date else transaction_date_str
        )
        itemization = []
        for i in range(nights):
            from datetime import date, timedelta
            try:
                base = date.fromisoformat(check_in)
                night_date = (base + timedelta(days=i)).isoformat()
            except (ValueError, TypeError):
                night_date = check_in
            itemization.append(HotelItemizationInput(
                nightDate=night_date,
                roomRate=rate,
                taxes=round(taxes / nights, 2),
            ))

    elif expense_type == "FLIGHT" and extracted.airfare_detail:
        ad = extracted.airfare_detail
        airfare_detail = AirfareDetailInput(
            origin=ad.origin,
            destination=ad.destination,
            travelClass=getattr(ad, "travel_class", None) or "ECONOMY",
            flightNumber=getattr(ad, "flight_number", None),
            ticketNumber=ad.ticket_number,
        )

    elif expense_type == "TAXI" and extracted.taxi_detail:
        td = extracted.taxi_detail
        taxi_detail = TaxiDetailInput(
            fromLocation=td.from_location,
            toLocation=td.to_location,
            distanceKm=td.distance_km,
        )

    elif expense_type == "MEAL" and extracted.meal_detail:
        md = extracted.meal_detail
        meal_detail = MealDetailInput(
            mealType=md.meal_type or "MEAL",
            attendees=md.num_attendees or 1,
        )

    return ExpenseInput(
        expenseType=expense_type,
        vendor=extracted.vendor or "UNKNOWN",
        amount=extracted.amount,
        currency=extracted.currency or "INR",
        transactionDate=transaction_date_str,
        city=extracted.city or "UNKNOWN",
        paymentType=payment_type,
        receiptId=receipt_id,
        ocrConfidence=getattr(extracted, "ocr_confidence", None),
        itemization=itemization,
        airfareDetail=airfare_detail,
        taxiDetail=taxi_detail,
        mealDetail=meal_detail,
    )


def build_receipt_register_request(
    extracted: ExtractedExpense,
    employee_id: str,
    filename: str,
    mime_type: str = "application/pdf",
) -> ReceiptRegisterRequest:
    """
    Build the metadata body for:
      POST /api/v4/receipts/register

    Returns a ReceiptRegisterRequest that concur_client.register_receipt() will post.
    The returned receiptId is then passed to build_expense_input() as receipt_id.
    """
    return ReceiptRegisterRequest(
        employeeId=employee_id,
        receiptHash=extracted.file_hash or "",
        fileName=filename,
        mimeType=mime_type,
        ocrConfidence=getattr(extracted, "ocr_confidence", None),
    )
