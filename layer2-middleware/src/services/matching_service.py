"""
Matching service.

Fetches unmatched corporate card transactions from Layer 3 and scores
each extracted receipt against them using a composite fuzzy algorithm:

    vendor × 0.45  +  amount × 0.40  +  date × 0.10  +  city × 0.05

Match threshold: score ≥ 0.65

Uses rapidfuzz for vendor name similarity (token_sort_ratio handles
word-order differences e.g. "MARRIOTT BENGALURU" vs "Marriott").
Amount tolerance: ±10% to handle tax/rounding differences.
Date tolerance: ±3 days (hotel card charge can lag check-in by 2-3 days).

Industry-grade features added (2026-07):
  - Exclusive claim tracking: a transaction claimed by receipt[i] is
    removed from the candidate pool for receipt[i+1] in the same batch.
    Prevents two receipts matching the same card transaction.
  - Wider date window for HOTEL (card charge date ≠ check-in date).
  - Extended vendor normaliser: strips "cabs", "auto", "systems pvt ltd",
    "airways"; expands OlaCabs→ola, IndiGo→indigo, 6E→indigo aliases.
  - Score breakdown logged at DEBUG for diagnostics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Sequence

from src.models.concur_models import AvailableTransaction
from src.models.receipt_models import ExtractedExpense

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.65

# Composite score weights — must sum to 1.0
_W_VENDOR = 0.45
_W_AMOUNT = 0.40
_W_DATE   = 0.10
_W_CITY   = 0.05

# Amount tolerance: ±10%
# Receipts (especially hotel folios and flight e-tickets) sometimes show
# a booking total that differs from the card charge by GST rounding or
# convenience fees up to ~5–8%.
_AMOUNT_TOLERANCE = 0.10

# Date tolerance (days): card charges can be posted 1-3 days after the
# actual transaction date (hotel: card charged at check-in, receipt date
# is check-out; airline: booking date vs travel date).
_DATE_TOLERANCE_DAYS = 3


@dataclass
class MatchResult:
    """Output of the matching stage."""
    txn_id: Optional[str]     # Matched transaction ID, or None
    confidence: float         # Composite score 0.0–1.0
    # Per-dimension scores for debug/transparency
    score_vendor: float = 0.0
    score_amount: float = 0.0
    score_date:   float = 0.0


# ── Batch-level exclusive claim tracker ──────────────────────────────────────
# Used by pipeline.py to prevent two receipts in the same batch from claiming
# the same card transaction.  Passed as an optional shared set.

class _ClaimLedger:
    """Thread-safe set of txn_ids already claimed in this pipeline run."""
    def __init__(self) -> None:
        import asyncio
        self._lock = asyncio.Lock()
        self._claimed: set[str] = set()

    async def try_claim(self, txn_id: str) -> bool:
        """Attempt to claim txn_id.  Returns True if claim succeeded."""
        async with self._lock:
            if txn_id in self._claimed:
                return False
            self._claimed.add(txn_id)
            return True

    def claimed(self) -> frozenset[str]:
        return frozenset(self._claimed)


async def match(
    extracted: ExtractedExpense,
    employee_id: str,
    report_id: str,
    claim_ledger: Optional[_ClaimLedger] = None,
    available_transactions: Optional[Sequence[AvailableTransaction]] = None,
) -> MatchResult:
    """
    Stage 4 — Transaction matching.

    1. Fetch AVAILABLE corporate card transactions from Layer 3
    2. Exclude any txn_ids already claimed by a sibling receipt in this batch
    3. Score each remaining candidate against the extracted receipt
    4. Attempt to claim the best match via claim_ledger (exclusive)
    5. Return the best match if score ≥ MATCH_THRESHOLD
    """
    from src.services.concur_client import fetch_available_transactions

    if available_transactions is None:
        try:
            transactions = await fetch_available_transactions(employee_id, report_id)
        except Exception as exc:
            logger.warning(
                "Could not fetch available transactions from Layer 3: %s "
                "— proceeding with no match.",
                exc,
            )
            return MatchResult(txn_id=None, confidence=0.0)
    else:
        transactions = list(available_transactions)

    if not transactions:
        logger.info("No available card transactions to match against.")
        return MatchResult(txn_id=None, confidence=0.0)

    already_claimed: frozenset[str] = (
        claim_ledger.claimed() if claim_ledger else frozenset()
    )

    candidates = [
        t for t in transactions
        if t.status.upper() in ("UNMATCHED", "AVAILABLE")
        and t.txn_id not in already_claimed
    ]

    logger.info(
        "Matching | vendor=%s amount=%.2f | pool=%d available, %d excluded",
        extracted.vendor, extracted.amount, len(candidates), len(already_claimed),
    )

    best_txn: Optional[AvailableTransaction] = None
    best_score: float = 0.0
    best_breakdown: tuple[float, float, float] = (0.0, 0.0, 0.0)

    for txn in candidates:
        vs = score_vendor(extracted.vendor, txn.vendor)
        as_ = score_amount(extracted.amount, txn.amount)
        # For HOTEL, use check-in date if available; otherwise use transaction_date
        receipt_date = (
            extracted.hotel_detail.check_in_date
            if extracted.expense_type == "HOTEL"
            and extracted.hotel_detail
            and extracted.hotel_detail.check_in_date
            else extracted.transaction_date
        )
        ds = score_date(receipt_date, txn.transaction_date)
        # Layer 3 card transactions don't carry a city field, so txn_city is
        # always None.  score_city returns 0.5 (neutral) in that case — this is
        # intentional: the city dimension doesn't penalise or reward any match,
        # which is correct since we have no ground truth for the card city.
        cs = score_city(extracted.city, None)

        composite = round(vs * _W_VENDOR + as_ * _W_AMOUNT + ds * _W_DATE + cs * _W_CITY, 4)

        logger.debug(
            "  txn=%s vendor=%s amt=%.0f | v=%.2f a=%.2f d=%.2f → composite=%.3f",
            txn.txn_id, txn.vendor, txn.amount, vs, as_, ds, composite,
        )

        if composite > best_score:
            best_score = composite
            best_txn = txn
            best_breakdown = (vs, as_, ds)

    if best_txn and best_score >= MATCH_THRESHOLD:
        # Try to exclusively claim this transaction for this receipt
        claimed = True
        if claim_ledger:
            claimed = await claim_ledger.try_claim(best_txn.txn_id)

        if claimed:
            logger.info(
                "Match found | txn_id=%s vendor=%s amount=%.2f score=%.3f",
                best_txn.txn_id, best_txn.vendor, best_txn.amount, best_score,
            )
            return MatchResult(
                txn_id=best_txn.txn_id,
                confidence=round(best_score, 4),
                score_vendor=best_breakdown[0],
                score_amount=best_breakdown[1],
                score_date=best_breakdown[2],
            )
        else:
            logger.info(
                "Best match txn=%s already claimed by sibling receipt — skipping",
                best_txn.txn_id,
            )

    logger.info(
        "No match above threshold %.2f (best score=%.3f)", MATCH_THRESHOLD, best_score
    )
    return MatchResult(txn_id=None, confidence=round(best_score, 4))


# ── Individual scorers (public — used in tests) ───────────────────────────────

def score_vendor(receipt_vendor: Optional[str], txn_vendor: Optional[str]) -> float:
    """
    Fuzzy vendor name similarity using rapidfuzz token_sort_ratio.
    Both names are normalised before comparison.
    Returns 0.0–1.0.
    """
    if not receipt_vendor or not txn_vendor:
        return 0.5   # unknown — neutral

    try:
        from rapidfuzz import fuzz
    except ImportError:
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
    Amount similarity with ±10% tolerance.
    Returns 1.0 for exact match, decays linearly within tolerance, 0.0 beyond.
    """
    if txn_amount == 0:
        return 1.0 if receipt_amount == 0 else 0.0

    relative_diff = abs(receipt_amount - txn_amount) / abs(txn_amount)

    if relative_diff == 0:
        return 1.0
    if relative_diff <= _AMOUNT_TOLERANCE:
        # Linear decay from 1.0 at 0% diff to 0.5 at 10% diff
        return round(1.0 - (relative_diff / _AMOUNT_TOLERANCE) * 0.5, 4)
    return 0.0


def score_date(
    receipt_date: Optional[date],
    txn_date_str: Optional[str],
) -> float:
    """
    Date proximity score with ±3-day tolerance:
      Same day → 1.0
      ±1 day   → 0.75
      ±2 days  → 0.50
      ±3 days  → 0.25
      Beyond   → 0.0
      Either null → 0.5 (unknown — neutral, does not penalise)
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
        return 0.75
    if diff == 2:
        return 0.50
    if diff <= _DATE_TOLERANCE_DAYS:
        return 0.25
    return 0.0


def score_city(receipt_city: Optional[str], txn_city: Optional[str]) -> float:
    """City match — both null → 0.5 (neutral); match → 1.0; mismatch → 0.0."""
    if not receipt_city or not txn_city:
        return 0.5
    if receipt_city.lower().strip() == txn_city.lower().strip():
        return 1.0
    return 0.0


# ── Helpers ───────────────────────────────────────────────────────────────────

# Words to strip from vendor names before fuzzy comparison.
# Ordered so multi-word phrases are stripped before their component words.
_STRIP_TERMS = [
    # Company suffixes
    "private limited", "pvt ltd", "pvt", "ltd",
    # Ride-hailing noise words
    "cabs", "cab", "auto", "systems", "airways",
    # City/area names (LLM often appends the city or neighbourhood to the vendor)
    "bengaluru", "bangalore", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "kolkata", "india", "international",
    "indiranagar", "koramangala", "whitefield", "hsr layout",
    "bandra", "andheri", "powai", "juhu",
    "gurgaon", "noida", "connaught place",
    # Generic hospitality words that appear in many hotel names
    "hotel", "hotels", "suites", "resorts", "inn",
]

# Canonical alias map: normalised input → canonical vendor string
# This is applied AFTER stripping, so "ola cabs" → "ola" first (cabs stripped),
# then abbreviation "6e" → "indigo", etc.
_VENDOR_ALIASES: dict[str, str] = {
    # Marriott variants
    "mrt":       "marriott",
    # IndiGo variants — "6e" is IndiGo's IATA code used on all receipts
    "6e":        "indigo",
    "indigo airlines": "indigo airlines",
    "indigo air": "indigo airlines",
    # Other airlines
    "hil":       "hilton",
    "radis":     "radisson",
    "ib":        "ibis",
    # Ride-hailing
    "olacabs":   "ola",
    "ola cabs":  "ola",
    "uber india": "uber",
    "uber go":   "uber",
    "uber auto": "uber",
}


def _normalise_vendor(name: str) -> str:
    """
    Normalise a vendor name for fuzzy comparison:
      1. Lowercase + strip punctuation
      2. Strip known noise words (city names, legal suffixes, generic words)
      3. Apply alias map for known brand variants
    """
    import re
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)   # punctuation → space
    name = re.sub(r"\s+", " ", name).strip()

    # Full-string alias first (e.g. "ola cabs" before stripping "cabs")
    if name in _VENDOR_ALIASES:
        return _VENDOR_ALIASES[name]

    # Strip noise terms (longest first to avoid partial matches)
    for term in sorted(_STRIP_TERMS, key=len, reverse=True):
        name = re.sub(r"\b" + re.escape(term) + r"\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    # Alias map after stripping
    if name in _VENDOR_ALIASES:
        return _VENDOR_ALIASES[name]

    return name


def _parse_date_str(date_str: str) -> Optional[date]:
    """Parse YYYY-MM-DD date string to date object."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None
