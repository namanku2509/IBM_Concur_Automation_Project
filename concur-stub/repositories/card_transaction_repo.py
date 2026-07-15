"""
repositories/card_transaction_repo.py
---------------------------------------
Database access layer for the CorporateCardTransaction domain.

The card matching query (used in Step 8 of the pipeline) lives here.
Matching logic: vendor substring (case-insensitive) + exact amount +
transaction_date within ±tolerance_days.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.corporate_card_transaction import CorporateCardTransaction


def get_by_id(txn_id: str, db: Session) -> CorporateCardTransaction | None:
    return db.get(CorporateCardTransaction, txn_id)


def create(txn: CorporateCardTransaction, db: Session) -> CorporateCardTransaction:
    db.add(txn)
    db.flush()
    return txn


def get_available_for_employee(
    employee_id: str,
    db: Session,
) -> list[CorporateCardTransaction]:
    """Return all AVAILABLE card transactions for an employee."""
    return (
        db.query(CorporateCardTransaction)
        .filter(
            CorporateCardTransaction.employee_id == employee_id,
            CorporateCardTransaction.status == "AVAILABLE",
        )
        .order_by(CorporateCardTransaction.transaction_date.desc())
        .all()
    )


def get_all_for_employee(
    employee_id: str,
    db: Session,
) -> list[CorporateCardTransaction]:
    """Return all card transactions for an employee regardless of status."""
    return (
        db.query(CorporateCardTransaction)
        .filter(CorporateCardTransaction.employee_id == employee_id)
        .order_by(CorporateCardTransaction.transaction_date.desc())
        .all()
    )


def find_matching_transaction(
    employee_id: str,
    vendor: str,
    amount: float,
    transaction_date: date,
    db: Session,
    date_tolerance_days: int = 2,
) -> CorporateCardTransaction | None:
    """
    Find the best AVAILABLE card transaction that matches an expense.

    Matching criteria:
      - employee_id: exact match
      - vendor: case-insensitive substring match (card vendor contains
        or is contained by the expense vendor)
      - amount: exact match (float comparison via DB)
      - transaction_date: within ±date_tolerance_days

    Returns the first match or None.
    Note: float equality on currency amounts is intentional — card feeds
    report exact amounts and the stub uses them without rounding.
    """
    window_start = transaction_date - timedelta(days=date_tolerance_days)
    window_end   = transaction_date + timedelta(days=date_tolerance_days)
    vendor_lower = vendor.lower()

    candidates = (
        db.query(CorporateCardTransaction)
        .filter(
            CorporateCardTransaction.employee_id == employee_id,
            CorporateCardTransaction.status == "AVAILABLE",
            CorporateCardTransaction.amount == amount,
            CorporateCardTransaction.transaction_date >= window_start,
            CorporateCardTransaction.transaction_date <= window_end,
        )
        .all()
    )

    # Apply vendor substring match in Python (SQLite LOWER + LIKE is
    # unreliable with Unicode — safer to handle in application layer)
    for txn in candidates:
        txn_vendor_lower = txn.vendor.lower()
        if vendor_lower in txn_vendor_lower or txn_vendor_lower in vendor_lower:
            return txn

    return None


def mark_matched(
    txn_id: str,
    expense_id: str,
    db: Session,
) -> None:
    """Mark a card transaction as MATCHED and link it to an expense."""
    txn = db.get(CorporateCardTransaction, txn_id)
    if txn:
        txn.status = "MATCHED"
        txn.matched_expense_id = expense_id
        db.flush()


def get_all(db: Session) -> list[CorporateCardTransaction]:
    """Return all card transactions (admin use)."""
    return (
        db.query(CorporateCardTransaction)
        .order_by(
            CorporateCardTransaction.employee_id,
            CorporateCardTransaction.transaction_date.desc(),
        )
        .all()
    )
