"""
models/corporate_card_transaction.py
-------------------------------------
SQLAlchemy ORM model for the `corporate_card_transactions` table.

Represents a transaction from the company's corporate credit card feed.
These are seeded at startup and can be injected via the admin API.

Status transitions:
  AVAILABLE → MATCHED  (when linked to an expense in Step 8)
  AVAILABLE → IGNORED  (future: manual dismissal — not in prototype scope)

Matching logic (Step 8 of the validation pipeline):
  - vendor: case-insensitive substring match
  - amount: exact match
  - transaction_date: within ±2 days of the expense transaction date
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class CorporateCardTransaction(Base):
    __tablename__ = "corporate_card_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    card_last_four: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="AVAILABLE", nullable=False)
    """Valid values: AVAILABLE | MATCHED | IGNORED"""

    matched_expense_id: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )
    """
    Denormalized reference — stored as plain string (no FK) to break the circular
    dependency with Expense.card_transaction_id.  Kept in sync by the repository
    layer when a card transaction is matched to an expense.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Employee", back_populates="card_transactions"
    )

    def __repr__(self) -> str:
        return (
            f"<CorporateCardTransaction id={self.id!r} employee={self.employee_id!r} "
            f"vendor={self.vendor!r} amount={self.amount} status={self.status!r}>"
        )
