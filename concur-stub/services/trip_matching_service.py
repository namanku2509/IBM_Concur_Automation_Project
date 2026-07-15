"""
services/trip_matching_service.py
----------------------------------
Business trip matching service.

Used in Step 5 of the 9-step validation pipeline.

Matching strategy (two-pass):

  Pass 1 — Primary match (preferred):
    Find a trip that satisfies ALL three criteria:
      a. Trip belongs to the submitting employee
      b. At least one expense's transactionDate falls within the trip's
         date window (extended by ±trip_date_tolerance_days on each end)
      c. The trip's destination_city matches at least one expense city
         (case-insensitive, whitespace-normalised)

  Pass 2 — Card transaction fallback:
    If Pass 1 finds nothing, look at any AVAILABLE corporate card
    transactions for the employee. For each transaction, check whether
    its transaction_date falls within any trip's date window.
    If found, return that trip (city match is not required for fallback).

  No match:
    Return None. The caller (expense_service) sets the report to
    MANUAL_REVIEW and attaches a TRIP_NOT_MATCHED warning.

This two-pass approach mirrors real Concur behavior where card feeds
provide a stronger signal than employee-entered dates alone.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from config import settings
from models.trip import Trip
from repositories import card_transaction_repo, trip_repo


def find_matching_trip(
    employee_id: str,
    expense_dates: "List[date]",
    expense_cities: "List[str]",
    db: Session,
    expense_vendors: "Optional[List[str]]" = None,
    expense_amounts: "Optional[List[float]]" = None,
) -> "Optional[Trip]":
    """
    Find the best matching active trip for a bulk expense submission.

    Parameters:
        employee_id:      The employee submitting the expenses.
        expense_dates:    All transactionDate values from the expense list.
        expense_cities:   All city values from the expense list.
        db:               SQLAlchemy session.
        expense_vendors:  Optional vendor names for card-fallback corroboration.
        expense_amounts:  Optional amounts (parallel to expense_vendors) for
                          tighter card-fallback matching.

    Returns a Trip instance or None.
    """
    tolerance = settings.trip_date_tolerance_days

    # ---- Pass 1: Primary match (city + date) -------------------------
    primary = trip_repo.find_matching_trip(
        employee_id=employee_id,
        expense_dates=expense_dates,
        expense_cities=expense_cities,
        db=db,
        date_tolerance_days=tolerance,
    )
    if primary:
        return primary

    # ---- Pass 2: Card transaction corroborating fallback -------------
    # Only consider card transactions whose vendor matches one of the
    # submitted expense vendors AND whose date is close to a submitted
    # expense date.  This prevents an unrelated card transaction from
    # spuriously confirming a trip for a completely different city.
    if not expense_vendors or not expense_amounts:
        return None

    # Build a lookup of (vendor_lower, amount) pairs from submitted expenses
    expense_vendor_amounts = list(zip(
        [v.lower().strip() for v in expense_vendors],
        expense_amounts,
    ))

    available_txns = card_transaction_repo.get_available_for_employee(
        employee_id, db
    )

    for txn in available_txns:
        txn_vendor_lower = txn.vendor.lower().strip()
        # Vendor AND amount must match one of the submitted expenses
        matched = any(
            (exp_v in txn_vendor_lower or txn_vendor_lower in exp_v)
            and abs(txn.amount - exp_amt) < 0.01
            for exp_v, exp_amt in expense_vendor_amounts
        )
        if not matched:
            continue
        # Date must be close to a submitted expense date
        if not any(
            abs((txn.transaction_date - ed).days) <= tolerance
            for ed in expense_dates
        ):
            continue
        fallback_trip = trip_repo.find_trip_by_date_window(
            employee_id=employee_id,
            check_date=txn.transaction_date,
            db=db,
            tolerance_days=tolerance,
        )
        if fallback_trip:
            return fallback_trip

    return None
