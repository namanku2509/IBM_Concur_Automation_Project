"""
models/expense_report.py
------------------------
SQLAlchemy ORM model for the `expense_reports` table.

An expense report is the container for all expenses belonging to one
business trip. It is created first (shell), then expenses are bulk-submitted.

Status lifecycle (see plan document — Report Lifecycle section):
  DRAFT → MANUAL_REVIEW → SUBMITTED → APPROVED | REJECTED

The `travel_policy_name` is copied from the employee at creation time
so that policy changes after creation do not retroactively affect
existing reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ExpenseReport(Base):
    __tablename__ = "expense_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trip_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("trips.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_name: Mapped[str] = mapped_column(String, nullable=False)
    business_purpose: Mapped[str] = mapped_column(String, nullable=False)
    travel_policy_name: Mapped[str] = mapped_column(
        String,
        ForeignKey("travel_policies.name", ondelete="RESTRICT"),
        nullable=False,
    )
    expense_category: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="DRAFT", nullable=False)
    """Valid values: DRAFT | MANUAL_REVIEW | SUBMITTED | APPROVED | REJECTED"""

    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="INR", nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Employee", back_populates="expense_reports"
    )
    trip: Mapped["Trip | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Trip", back_populates="expense_reports"
    )
    expenses: Mapped[list["Expense"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Expense",
        back_populates="report",
        cascade="all, delete-orphan",
        foreign_keys="Expense.report_id",
    )

    def __repr__(self) -> str:
        return (
            f"<ExpenseReport id={self.id!r} employee={self.employee_id!r} "
            f"status={self.status!r} total={self.total_amount}>"
        )
