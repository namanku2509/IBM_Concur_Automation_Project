"""
repositories/receipt_repo.py
------------------------------
Database access layer for the Receipt domain.

Duplicate detection queries are centralised here.
The receipt_hash index on the table makes these lookups fast.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.receipt import Receipt


def create(receipt: Receipt, db: Session) -> Receipt:
    db.add(receipt)
    db.flush()
    return receipt


def get_by_id(receipt_id: str, db: Session) -> Receipt | None:
    return db.get(Receipt, receipt_id)


def find_by_hash(
    receipt_hash: str,
    employee_id: str,
    db: Session,
) -> Receipt | None:
    """
    Find an existing receipt by its SHA-256 hash for the same employee.
    Used by duplicate_detection.py (Step 6 of the pipeline).
    Returns the first match or None.
    """
    return (
        db.query(Receipt)
        .filter(
            Receipt.receipt_hash == receipt_hash,
            Receipt.employee_id == employee_id,
        )
        .first()
    )


def get_for_employee(employee_id: str, db: Session) -> list[Receipt]:
    """Return all receipts registered by an employee, most recent first."""
    return (
        db.query(Receipt)
        .filter(Receipt.employee_id == employee_id)
        .order_by(Receipt.registered_at.desc())
        .all()
    )


def hash_exists(receipt_hash: str, employee_id: str, db: Session) -> bool:
    """
    Fast existence check — avoids loading the full row.
    Returns True if a receipt with this hash already exists for this employee.
    """
    return (
        db.query(Receipt.id)
        .filter(
            Receipt.receipt_hash == receipt_hash,
            Receipt.employee_id == employee_id,
        )
        .first()
    ) is not None
