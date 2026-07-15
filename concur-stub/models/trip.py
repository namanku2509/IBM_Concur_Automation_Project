"""
models/trip.py
--------------
SQLAlchemy ORM model for the `trips` table.

A trip represents a business travel event associated with one employee.
Expense reports are matched against trips during the validation pipeline
(Step 5) using date window and destination city matching.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_city: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="ACTIVE", nullable=False)
    """Valid values: PLANNED | ACTIVE | COMPLETED"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Employee", back_populates="trips"
    )
    expense_reports: Mapped[list["ExpenseReport"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExpenseReport", back_populates="trip"
    )

    def __repr__(self) -> str:
        return (
            f"<Trip id={self.id!r} employee={self.employee_id!r} "
            f"city={self.destination_city!r} {self.start_date}→{self.end_date}>"
        )
