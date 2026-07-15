"""
models/employee.py
------------------
SQLAlchemy ORM model for the `employees` table.

Employees are the acting principals throughout the system.
Every expense report, trip, and card transaction is owned by an employee.
The `travel_policy_name` FK replaces the old grade-based model — policy is
now the first-class assignment unit, making policy changes immediately
visible without modifying employee records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    travel_policy_name: Mapped[str] = mapped_column(
        String,
        ForeignKey("travel_policies.name", ondelete="RESTRICT"),
        nullable=False,
    )
    department: Mapped[str] = mapped_column(String, nullable=False)
    manager_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    travel_policy: Mapped["TravelPolicy"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "TravelPolicy", back_populates="employees"
    )
    expense_reports: Mapped[list["ExpenseReport"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExpenseReport", back_populates="employee", cascade="all, delete-orphan"
    )
    trips: Mapped[list["Trip"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Trip", back_populates="employee", cascade="all, delete-orphan"
    )
    card_transactions: Mapped[list["CorporateCardTransaction"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CorporateCardTransaction", back_populates="employee"
    )
    receipts: Mapped[list["Receipt"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Receipt", back_populates="employee"
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} name={self.name!r} policy={self.travel_policy_name!r}>"
