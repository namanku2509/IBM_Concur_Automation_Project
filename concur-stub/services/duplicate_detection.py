"""
services/duplicate_detection.py
---------------------------------
Receipt duplicate detection service.

Used in Step 6 of the 9-step validation pipeline.

Algorithm:
  1. Compute a deterministic SHA-256 hash of the key receipt fields.
  2. Query the `receipts` table for an existing row with the same hash
     for the same employee.
  3. Return (is_duplicate, existing_receipt_id) to the caller.

Hash input format (colon-delimited, all lowercase / normalised):
    vendor.lower() + ":" + str(amount) + ":" + str(transaction_date) + ":" + employee_id

This hash is intentionally insensitive to:
  - Filename, MIME type, OCR confidence (metadata — not identity)
  - Time of day (only the date is used)

And intentionally sensitive to:
  - Vendor name (case-normalised)
  - Exact amount (different split-bill amounts → different hashes)
  - Transaction date
  - Employee (two employees can legitimately share a vendor/amount/date)
"""

from __future__ import annotations

import hashlib
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from repositories import receipt_repo


def compute_receipt_hash(
    vendor: str,
    amount: float,
    transaction_date: str,  # ISO 8601 string: "YYYY-MM-DD"
    employee_id: str,
) -> str:
    """
    Compute the SHA-256 duplicate-detection hash for a receipt.

    Parameters match the fields available in ExpenseInput before
    any DB interaction occurs.

    Returns a 64-character lowercase hex string.
    """
    raw = f"{vendor.lower().strip()}:{amount}:{transaction_date}:{employee_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_duplicate(
    receipt_hash: str,
    employee_id: str,
    db: Session,
) -> "Tuple[bool, Optional[str]]":
    """
    Check whether a receipt with the given hash already exists for this employee.

    Returns:
        (True, existing_receipt_id)  — if a duplicate is found
        (False, None)                — if no duplicate exists
    """
    existing = receipt_repo.find_by_hash(receipt_hash, employee_id, db)
    if existing:
        return True, existing.id
    return False, None
