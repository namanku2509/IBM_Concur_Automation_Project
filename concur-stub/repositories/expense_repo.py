"""
repositories/expense_repo.py
------------------------------
Database access layer for the Expense domain and all its
type-specific detail tables (hotel itemization, airfare, taxi, meal).
"""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from models.expense import Expense
from models.hotel_itemization import HotelItemizationLine
from models.airfare_detail import AirfareDetail
from models.taxi_detail import TaxiDetail
from models.meal_detail import MealDetail


# ------------------------------------------------------------------ #
# Expense                                                              #
# ------------------------------------------------------------------ #

def create(expense: Expense, db: Session) -> Expense:
    db.add(expense)
    db.flush()
    return expense


def get_by_id(expense_id: str, db: Session) -> Expense | None:
    return (
        db.query(Expense)
        .options(
            joinedload(Expense.hotel_itemization_lines),
            joinedload(Expense.airfare_detail),
            joinedload(Expense.taxi_detail),
            joinedload(Expense.meal_detail),
        )
        .filter(Expense.id == expense_id)
        .first()
    )


def get_for_report(report_id: str, db: Session) -> list[Expense]:
    """Return all top-level expenses for a report (no itemization children)."""
    return (
        db.query(Expense)
        .options(
            joinedload(Expense.hotel_itemization_lines),
            joinedload(Expense.airfare_detail),
            joinedload(Expense.taxi_detail),
            joinedload(Expense.meal_detail),
        )
        .filter(
            Expense.report_id == report_id,
            Expense.parent_expense_id.is_(None),
        )
        .order_by(Expense.created_at)
        .all()
    )


def update_status(expense_id: str, status: str, db: Session) -> None:
    expense = db.get(Expense, expense_id)
    if expense:
        expense.status = status
        db.flush()


def link_card_transaction(
    expense_id: str,
    card_transaction_id: str,
    db: Session,
) -> None:
    expense = db.get(Expense, expense_id)
    if expense:
        expense.card_transaction_id = card_transaction_id
        expense.status = "MATCHED"
        db.flush()


def link_receipt(expense_id: str, receipt_id: str, db: Session) -> None:
    expense = db.get(Expense, expense_id)
    if expense:
        expense.receipt_id = receipt_id
        db.flush()


# ------------------------------------------------------------------ #
# Hotel itemization lines                                              #
# ------------------------------------------------------------------ #

def create_itemization_line(
    line: HotelItemizationLine,
    db: Session,
) -> HotelItemizationLine:
    db.add(line)
    db.flush()
    return line


def get_itemization_for_expense(
    expense_id: str,
    db: Session,
) -> list[HotelItemizationLine]:
    return (
        db.query(HotelItemizationLine)
        .filter(HotelItemizationLine.expense_id == expense_id)
        .order_by(HotelItemizationLine.night_date)
        .all()
    )


# ------------------------------------------------------------------ #
# Type-specific detail tables                                          #
# ------------------------------------------------------------------ #

def create_airfare_detail(detail: AirfareDetail, db: Session) -> AirfareDetail:
    db.add(detail)
    db.flush()
    return detail


def create_taxi_detail(detail: TaxiDetail, db: Session) -> TaxiDetail:
    db.add(detail)
    db.flush()
    return detail


def create_meal_detail(detail: MealDetail, db: Session) -> MealDetail:
    db.add(detail)
    db.flush()
    return detail
