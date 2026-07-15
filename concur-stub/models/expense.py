"""
models/expense.py
-----------------
SQLAlchemy ORM model for the `expenses` table.

Represents a single expense line within an expense report.
Hotel expenses use the parent_expense_id self-referential FK for
itemization children (the plan's parent/child model).

Status values:
  MATCHED      — corporate card transaction successfully linked
  PENDING      — CORPORATE_CARD payment type but no card match found
  MANUAL_REVIEW — duplicate detected, or missing fields, or other issue
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("expense_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_expense_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=True,
    )
    expense_type: Mapped[str] = mapped_column(String, nullable=False)
    """Valid values: HOTEL | MEAL | TAXI | FLIGHT"""

    vendor: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    payment_type: Mapped[str] = mapped_column(String, nullable=False)
    """Valid values: CORPORATE_CARD | PERSONAL_CASH | CORPORATE_CASH"""

    card_transaction_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("corporate_card_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    receipt_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("receipts.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="PENDING", nullable=False)
    """Valid values: PENDING | MATCHED | MANUAL_REVIEW"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    report: Mapped["ExpenseReport"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExpenseReport",
        back_populates="expenses",
        foreign_keys=[report_id],
    )
    hotel_itemization_lines: Mapped[list["HotelItemizationLine"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "HotelItemizationLine",
        back_populates="expense",
        cascade="all, delete-orphan",
    )
    airfare_detail: Mapped["AirfareDetail | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "AirfareDetail",
        back_populates="expense",
        cascade="all, delete-orphan",
        uselist=False,
    )
    taxi_detail: Mapped["TaxiDetail | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "TaxiDetail",
        back_populates="expense",
        cascade="all, delete-orphan",
        uselist=False,
    )
    meal_detail: Mapped["MealDetail | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "MealDetail",
        back_populates="expense",
        cascade="all, delete-orphan",
        uselist=False,
    )
    card_transaction: Mapped["CorporateCardTransaction | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CorporateCardTransaction",
        foreign_keys=[card_transaction_id],
        uselist=False,
    )
    receipt: Mapped["Receipt | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Receipt",
        back_populates="expense",
        foreign_keys=[receipt_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Expense id={self.id!r} type={self.expense_type!r} "
            f"vendor={self.vendor!r} amount={self.amount} status={self.status!r}>"
        )
