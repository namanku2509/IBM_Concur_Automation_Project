"""
Extraction service — Ollama (local LLM, no API key needed).

Uses llama3.2:3b running locally via Ollama with type-specific prompts
grounded in Layer 3's exact DB schema field names to extract structured
data from raw OCR text — regardless of the receipt's print format.

Falls back to heuristic regex extraction if Ollama is not running.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Optional

from src import config
from src.models.receipt_models import (
    AirfareDetail,
    CategorisationResult,
    ExtractedExpense,
    HotelDetail,
    MealDetail,
    OcrResult,
    RegistrationDetail,
    TaxiDetail,
)
from src.prompts.extraction_prompt import (
    EXTRACTION_SYSTEM_PROMPT,
    extraction_user_prompt,
)
from src.services.categorisation_service import _extract_json

logger = logging.getLogger(__name__)


async def extract(
    ocr_result: OcrResult,
    cat_result: CategorisationResult,
) -> ExtractedExpense:
    """Stage 3 — Intelligent field extraction via local Ollama LLM."""
    if not config.ollama_configured():
        logger.warning("Ollama not running — using heuristic extraction fallback.")
        return _heuristic_fallback(ocr_result, cat_result)

    try:
        raw_response = _call_ollama_extraction(ocr_result.raw_text, cat_result.expense_type)
        parsed = _extract_json(raw_response)
        logger.debug("Ollama extraction parsed fields: %s", list(parsed.keys()))
        return _build_extracted_expense(parsed, cat_result.expense_type, ocr_result)
    except Exception as exc:
        logger.warning("Ollama extraction failed: %s — using heuristic fallback", exc)
        return _heuristic_fallback(ocr_result, cat_result)


def _call_ollama_extraction(raw_text: str, expense_type: str) -> str:
    """Call local Ollama for extraction and return raw response."""
    try:
        import ollama
    except ImportError:
        raise RuntimeError("ollama package not installed. Run: pip install ollama")

    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"{extraction_user_prompt(raw_text, expense_type)}"
    )

    response = ollama.generate(
        model=config.OLLAMA_MODEL,
        prompt=prompt,
        options={
            "temperature": config.OLLAMA_PARAMS["temperature"],
            "num_predict": config.OLLAMA_PARAMS["num_predict"],
        },
    )
    result = response.get("response", "")
    logger.debug("Ollama extraction response: %s", result[:400])
    return result


def _build_extracted_expense(
    parsed: dict,
    expense_type: str,
    ocr_result: OcrResult,
) -> ExtractedExpense:
    vendor = _str_or_none(parsed.get("vendor"))
    raw_amount = _safe_float(parsed.get("amount"), default=0.0)
    # ── Post-extraction amount validator ──────────────────────────────────────
    # Sanity-check: the LLM's extracted amount must actually appear in the OCR
    # text (within 1%). If it doesn't, fall back to the labelled-total extractor.
    amount = _validate_amount_in_text(raw_amount, ocr_result.raw_text, expense_type)
    currency = _str_or_none(parsed.get("currency")) or "INR"
    transaction_date = _parse_date(parsed.get("transaction_date"))
    city = _str_or_none(parsed.get("city"))

    hotel_detail = airfare_detail = taxi_detail = meal_detail = registration_detail = None

    if expense_type == "HOTEL":
        check_in  = _parse_date(parsed.get("check_in_date"))
        check_out = _parse_date(parsed.get("check_out_date"))

        # Always compute num_nights from dates — never trust the LLM's value
        if check_in and check_out and check_out > check_in:
            num_nights = (check_out - check_in).days
        else:
            num_nights = _safe_int(parsed.get("num_nights"))

        # Compute nightly_rate from accommodation charges / num_nights
        # Use LLM value only if it gave one; otherwise derive from total and nights
        nightly_rate = _safe_float(parsed.get("nightly_rate"))
        if nightly_rate is None and num_nights and num_nights > 0:
            room_amount = _safe_float(parsed.get("amount"), default=0.0)
            if room_amount and room_amount > 0:
                nightly_rate = round(room_amount / num_nights, 2)

        hotel_detail = HotelDetail(
            check_in_date=check_in,
            check_out_date=check_out,
            num_nights=num_nights,
            nightly_rate=nightly_rate,
            tax_amount=_safe_float(parsed.get("tax_amount"), default=0.0),
        )
    elif expense_type == "FLIGHT":
        airfare_detail = AirfareDetail(
            origin=_str_or_none(parsed.get("origin")),
            destination=_str_or_none(parsed.get("destination")),
            airline=_str_or_none(parsed.get("airline")),
            ticket_number=_str_or_none(parsed.get("ticket_number")),
            travel_class=_str_or_none(parsed.get("travel_class")),
            passenger_name=_str_or_none(parsed.get("passenger_name")),
        )
    elif expense_type == "TAXI":
        # If LLM missed distance_km, fall back to regex over the raw OCR text
        distance_km = _safe_float(parsed.get("distance_km"))
        if distance_km is None:
            distance_km = _extract_distance_km(ocr_result.raw_text)
        taxi_detail = TaxiDetail(
            from_location=_str_or_none(parsed.get("from_location")),
            to_location=_str_or_none(parsed.get("to_location")),
            distance_km=distance_km,
        )
    elif expense_type == "MEALS":
        meal_detail = MealDetail(
            meal_type=_str_or_none(parsed.get("meal_type")),
            num_attendees=_safe_int(parsed.get("num_attendees")) or 1,
            business_justification=_str_or_none(parsed.get("business_justification")),
        )
    elif expense_type == "REGISTRATION":
        registration_detail = RegistrationDetail(
            event_name=_str_or_none(parsed.get("event_name")),
            event_date=_parse_date(parsed.get("event_date")),
            registration_id=_str_or_none(parsed.get("registration_id")),
            organiser=_str_or_none(parsed.get("organiser")),
        )

    return ExtractedExpense(
        expense_type=expense_type,
        vendor=vendor,
        amount=amount,
        currency=currency,
        transaction_date=transaction_date,
        city=city,
        ocr_engine=ocr_result.engine_used,
        file_hash=ocr_result.file_hash,
        ocr_raw_text=ocr_result.raw_text,
        hotel_detail=hotel_detail,
        airfare_detail=airfare_detail,
        taxi_detail=taxi_detail,
        meal_detail=meal_detail,
        registration_detail=registration_detail,
    )


def _heuristic_fallback(ocr_result: OcrResult, cat_result: CategorisationResult) -> ExtractedExpense:
    raw_text = ocr_result.raw_text
    return ExtractedExpense(
        expense_type=cat_result.expense_type,
        vendor=_extract_vendor_from_first_line(raw_text),
        amount=_extract_max_amount(raw_text) or 0.0,
        currency="INR",
        transaction_date=_extract_first_date(raw_text),
        city=None,
        ocr_engine=ocr_result.engine_used,
        file_hash=ocr_result.file_hash,
        ocr_raw_text=raw_text,
    )


# ── Type coercions ────────────────────────────────────────────────────────────

def _str_or_none(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none", "n/a", "") else None


def _safe_float(val, default: Optional[float] = None) -> Optional[float]:
    if val is None:
        return default
    try:
        # Strip currency prefixes like "INR ", "Rs. ", "₹" before parsing
        cleaned = re.sub(r"[^\d.,\-]", "", str(val)).replace(",", "").strip()
        return float(cleaned) if cleaned else default
    except (ValueError, TypeError):
        return default


def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def _parse_date(val) -> Optional[date]:
    if val is None:
        return None
    s = str(val).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _extract_max_amount(text: str) -> Optional[float]:
    amounts = re.findall(r"(?:₹|Rs\.?\s?|INR\s?)(\d[\d,]*(?:\.\d{1,2})?)", text)
    if not amounts:
        amounts = re.findall(r"\b(\d{3,6}(?:\.\d{1,2})?)\b", text)
    if not amounts:
        return None
    return max(float(a.replace(",", "")) for a in amounts)


def _extract_labelled_total(text: str) -> Optional[float]:
    """
    Extract the amount next to an explicit total label.
    Checks for common total labels in priority order:
      TOTAL FARE, TOTAL AMOUNT DUE, TOTAL AMOUNT, GRAND TOTAL,
      AMOUNT PAID, AMOUNT DUE, TOTAL BILL, TOTAL:
    Returns the FIRST labelled total found (most specific wins).
    """
    # Priority patterns — ordered from most to least specific
    patterns = [
        r"TOTAL\s+FARE\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"TOTAL\s+AMOUNT\s+DUE\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"TOTAL\s+AMOUNT\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"GRAND\s+TOTAL\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"AMOUNT\s+PAID\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"AMOUNT\s+DUE\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"TOTAL\s+BILL\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
        r"(?:^|\n)\s*TOTAL\s*[:\-]\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except (ValueError, TypeError):
                continue
    return None


def _all_amounts_in_text(text: str) -> list[float]:
    """
    Return all distinct monetary amounts found in the OCR text.
    Only looks for amounts preceded by a currency marker (INR, Rs, ₹)
    OR amounts that look like prices (reasonable range: 1–999999).
    Explicitly filters out phone numbers, PIN codes, IDs, etc.
    """
    result = []
    seen = set()

    # Priority: currency-prefixed amounts — most reliable
    currency_matches = re.findall(
        r"(?:INR|Rs\.?\s*|₹)\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    for r in currency_matches:
        try:
            v = float(r.replace(",", ""))
            if 1.0 <= v <= 999999.0 and v not in seen:
                seen.add(v)
                result.append(v)
        except (ValueError, TypeError):
            continue

    # If no currency-prefixed amounts found, fall back to plain numbers
    # but filter out known non-amount patterns
    if not result:
        # Remove phone numbers, PIN codes, IDs before scanning
        cleaned = re.sub(r"\b0\d{9,}\b", " ", text)       # phone: starts with 0, 10+ digits
        cleaned = re.sub(r"\b\d{6,}\b", " ", cleaned)      # remove 6+ digit numbers (IDs, PINs)
        cleaned = re.sub(r"\b\d{1,3}\b", " ", cleaned)     # remove 1-3 digit numbers (days, seats, area codes)
        # Also strip partial phone fragments like "0124" "6173" "838" from dashed numbers
        cleaned = re.sub(r"\b\d{3,4}\b(?=[-\s]\d{4})", " ", cleaned)  # remove leading segments of dashed phones
        plain = re.findall(r"\b(\d{4,5}(?:\.\d{1,2})?)\b", cleaned)   # minimum 4 digits for plain fallback
        for r in plain:
            try:
                v = float(r.replace(",", ""))
                if 200.0 <= v <= 99999.0 and v not in seen:
                    seen.add(v)
                    result.append(v)
            except (ValueError, TypeError):
                continue

    return result


# Minimum plausible amounts per expense type (INR).
# Prevents phone number fragments and noise from being accepted as valid totals.
_MIN_AMOUNT_BY_TYPE: dict[str, float] = {
    "FLIGHT":       500.0,   # cheapest Indian domestic ticket is ~₹1000+
    "HOTEL":        500.0,   # cheapest hotel night ₹500+
    "TAXI":          50.0,   # minimum cab fare
    "MEALS":         30.0,   # minimum meal
    "MEAL":          30.0,
    "REGISTRATION": 100.0,
}


def _validate_amount_in_text(
    llm_amount: Optional[float],
    ocr_text: str,
    expense_type: str,
) -> float:
    """
    Validate that the LLM-extracted amount actually appears in the OCR text.
    If it doesn't (within 1% tolerance), fall back to the labelled total,
    then to the largest amount in text.

    Also enforces a minimum plausible amount per expense type to reject
    phone number fragments (e.g. 124 from 0124-6173838) being accepted.
    """
    min_amount = _MIN_AMOUNT_BY_TYPE.get(expense_type, 30.0)

    if llm_amount is None or llm_amount <= 0:
        # LLM gave nothing useful — use labelled total or max
        return _extract_labelled_total(ocr_text) or _extract_max_amount(ocr_text) or 0.0

    # Sanity check: reject amounts below type-specific minimum — they are almost
    # certainly noise (phone fragments, seat numbers, page numbers, etc.)
    if llm_amount < min_amount:
        logger.warning(
            "Amount %.2f is below minimum %.2f for %s — treating as noise, "
            "falling back to labelled total",
            llm_amount, min_amount, expense_type,
        )
        return _extract_labelled_total(ocr_text) or _extract_max_amount(ocr_text) or 0.0

    # Check if llm_amount is literally present in the OCR text (within 1%)
    all_amounts = _all_amounts_in_text(ocr_text)
    for a in all_amounts:
        if a > 0 and abs(llm_amount - a) / a <= 0.01:
            # Amount is present in the text — LLM is correct
            logger.debug("Amount %.2f validated in OCR text ✓", llm_amount)
            return llm_amount

    # LLM amount not found in text — it hallucinated or used wrong receipt
    logger.warning(
        "Amount %.2f from LLM NOT found in OCR text (candidates: %s) — "
        "falling back to labelled total",
        llm_amount, all_amounts[:8],
    )
    labelled = _extract_labelled_total(ocr_text)
    if labelled:
        logger.info("Using labelled total %.2f instead of LLM amount %.2f", labelled, llm_amount)
        return labelled

    # Last resort — largest amount in text
    max_amt = _extract_max_amount(ocr_text)
    if max_amt:
        logger.info("Using max amount %.2f as last resort", max_amt)
        return max_amt

    return llm_amount  # Give up and trust LLM


def _extract_distance_km(text: str) -> Optional[float]:
    """Extract distance value from text. Handles '8.32 kilometres', '12 km', '5.4 kms'."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:kilometres?|kilometers?|kms?|km)\b", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _extract_first_date(text: str) -> Optional[date]:
    for pattern in [r"(\d{4}-\d{2}-\d{2})", r"(\d{1,2}/\d{1,2}/\d{4})", r"(\d{1,2}-\d{1,2}-\d{4})"]:
        m = re.search(pattern, text)
        if m:
            result = _parse_date(m.group(1))
            if result:
                return result
    return None


def _extract_vendor_from_first_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and len(stripped) > 2:
            return stripped[:80]
    return None
