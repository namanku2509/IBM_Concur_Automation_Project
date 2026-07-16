"""
Matching service.

Fetches unmatched corporate card transactions from Layer 3 and scores
each extracted receipt against them using a composite fuzzy algorithm:

    vendor × 0.40  +  amount × 0.40  +  date × 0.15  +  city × 0.05

Match threshold: score ≥ 0.80

Uses rapidfuzz for vendor name similarity (token_sort_ratio handles
word-order differences e.g. "MARRIOTT BENGALURU" vs "Marriott").
Amount tolerance: ±2% to handle FX rounding and convenience fees.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from src.models.concur_models import AvailableTransaction
from src.models.receipt_models import ExtractedExpense

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.72

# Composite score weights — must sum to 1.0
_W_VENDOR = 0.40
_W_AMOUNT = 0.40
_W_DATE = 0.15
_W_CITY = 0.05

# Amount tolerance: ±10%
# Increased from 2% — OCR on image-based PDFs (ChatGPT receipts, scans)
# can introduce rounding errors, and real booking confirmations sometimes
# show slightly different amounts than what was charged to the card.
_AMOUNT_TOLERANCE = 0.10


@dataclass
class MatchResult:
    """Output of the matching stage."""
    txn_id: Optional[str]     # Matched transaction ID, or None
    confidence: float         # Composite score 0.0–1.0


async def match(
    extracted: ExtractedExpense,
    employee_id: str,
    report_id: str,
) -> MatchResult:
    """
    Stage 4 — Transaction matching.

    1. Fetch UNMATCHED corporate card transactions from Layer 3
    2. Score each against the extracted receipt
    3. Return the best match if score ≥ MATCH_THRESHOLD
    """
    from src.services.concur_client import fetch_available_transactions

    try:
        transactions = await fetch_available_transactions(employee_id, report_id)
    except Exception as exc:
        logger.warning(
            "Could not fetch available transactions from Layer 3: %s "
            "— proceeding with no match.",
            exc,
        )
        return MatchResult(txn_id=None, confidence=0.0)

    if not transactions:
        logger.info("No available card transactions to match against.")
        return MatchResult(txn_id=None, confidence=0.0)

    candidates = [t for t in transactions if t.status.upper() in ("UNMATCHED", "AVAILABLE")]
    logger.info(
        "Matching | receipt_vendor=%s amount=%.2f | candidates=%d",
        extracted.vendor, extracted.amount, len(candidates),
    )

    best_txn: Optional[AvailableTransaction] = None
    best_score: float = 0.0

    for txn in candidates:
        score = _composite_score(extracted, txn)
        logger.debug(
            "  Candidate txn_id=%s vendor=%s amount=%.2f → score=%.3f",
            txn.txn_id, txn.vendor, txn.amount, score,
        )
        if score > best_score:
            best_score = score
            best_txn = txn

    if best_txn and best_score >= MATCH_THRESHOLD:
        logger.info(
            "Match found | txn_id=%s vendor=%s amount=%.2f score=%.3f",
            best_txn.txn_id, best_txn.vendor, best_txn.amount, best_score,
        )
        return MatchResult(txn_id=best_txn.txn_id, confidence=round(best_score, 4))

    logger.info(
        "No match above threshold %.2f (best score=%.3f)", MATCH_THRESHOLD, best_score
    )
    return MatchResult(txn_id=None, confidence=round(best_score, 4))


# ── Composite scorer ──────────────────────────────────────────────────────────

def _composite_score(extracted: ExtractedExpense, txn: AvailableTransaction) -> float:
    vs = score_vendor(extracted.vendor, txn.vendor)
    as_ = score_amount(extracted.amount, txn.amount)
    ds = score_date(extracted.transaction_date, txn.transaction_date)
    cs = score_city(extracted.city, None)   # Layer 3 txn has no city field

    composite = vs * _W_VENDOR + as_ * _W_AMOUNT + ds * _W_DATE + cs * _W_CITY
    return round(composite, 4)


# ── Individual scorers (public — used in tests) ───────────────────────────────

def score_vendor(receipt_vendor: Optional[str], txn_vendor: Optional[str]) -> float:
    """
    Fuzzy vendor name similarity using rapidfuzz token_sort_ratio.
    token_sort_ratio handles word-order differences:
      "MARRIOTT BENGALURU" vs "Marriott" → high score
    Returns 0.0–1.0.
    """
    if not receipt_vendor or not txn_vendor:
        return 0.5   # unknown — neutral score, not a dealbreaker

    try:
        from rapidfuzz import fuzz
    except ImportError:
        # Fallback: simple case-insensitive substring check
        r = receipt_vendor.lower().strip()
        t = txn_vendor.lower().strip()
        if r == t:
            return 1.0
        if r in t or t in r:
            return 0.7
        return 0.0

    ratio = fuzz.token_sort_ratio(
        _normalise_vendor(receipt_vendor),
        _normalise_vendor(txn_vendor),
    )
    return round(ratio / 100.0, 4)


def score_amount(receipt_amount: float, txn_amount: float) -> float:
    """
    Amount similarity with ±2% tolerance.
    Returns 1.0 for exact match, decays linearly within tolerance, 0.0 beyond.
    """
    if txn_amount == 0:
        return 1.0 if receipt_amount == 0 else 0.0

    relative_diff = abs(receipt_amount - txn_amount) / abs(txn_amount)

    if relative_diff == 0:
        return 1.0
    if relative_diff <= _AMOUNT_TOLERANCE:
        # Linear decay from 1.0 at 0% diff to 0.5 at ±2% diff
        return round(1.0 - (relative_diff / _AMOUNT_TOLERANCE) * 0.5, 4)
    return 0.0


def score_date(
    receipt_date: Optional[date],
    txn_date_str: Optional[str],
) -> float:
    """
    Date proximity score:
      Same day   → 1.0
      ±1 day     → 0.5
      ±2 days    → 0.25
      Beyond     → 0.0
      Either null → 0.5 (unknown — neutral)
    """
    if receipt_date is None or txn_date_str is None:
        return 0.5

    txn_date = _parse_date_str(txn_date_str)
    if txn_date is None:
        return 0.5

    diff = abs((receipt_date - txn_date).days)

    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5
    if diff == 2:
        return 0.25
    return 0.0


def score_city(receipt_city: Optional[str], txn_city: Optional[str]) -> float:
    """
    City match score:
      Both null    → 0.5 (unknown — neutral)
      Match        → 1.0
      Mismatch     → 0.0
    """
    if not receipt_city or not txn_city:
        return 0.5
    if receipt_city.lower().strip() == txn_city.lower().strip():
        return 1.0
    return 0.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_vendor(name: str) -> str:
    """
    Normalise a vendor name for fuzzy comparison:
    - Lowercase
    - Strip punctuation
    - Strip common city suffixes (e.g. "Marriott Bengaluru" → "Marriott")
    - Expand common abbreviations
    """
    import re
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)  # strip punctuation
    name = re.sub(r"\s+", " ", name)      # collapse whitespace

    # Strip city names appended by LLM extraction
    _CITY_SUFFIXES = [
        "bengaluru", "bangalore", "mumbai", "delhi", "hyderabad",
        "chennai", "pune", "kolkata", "india", "international",
        "hotel", "pvt ltd", "pvt", "ltd", "private limited",
    ]
    for city in _CITY_SUFFIXES:
        name = re.sub(r"\b" + city + r"\b", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip()

    abbreviations = {
        "mrt": "marriott",
        "hil": "hilton",
        "hyatt": "hyatt",
        "radis": "radisson",
        "ib": "ibis",
        "6e": "indigo",
        "indigo airlines": "indigo airlines",
    }
    for abbr, full in abbreviations.items():
        if name.strip() == abbr:
            name = full

    return name.strip()


def _parse_date_str(date_str: str) -> Optional[date]:
    """Parse YYYY-MM-DD date string to date object."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None
