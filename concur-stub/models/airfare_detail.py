"""
models/airfare_detail.py
------------------------
SQLAlchemy ORM model for the `airfare_details` table.

One-to-one with an expense of type FLIGHT.
The travel_class field is validated by TravelClassValidator in the
policy engine against the MAX_TRAVEL_CLASS rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AirfareDetail(Base):
    __tablename__ = "airfare_details"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    expense_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    origin: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    flight_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    travel_class: Mapped[str] = mapped_column(String, nullable=False, default="ECONOMY")
    """Valid values: ECONOMY | BUSINESS"""

    ticket_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship
    expense: Mapped["Expense"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Expense", back_populates="airfare_detail"
    )

    def __repr__(self) -> str:
        return (
            f"<AirfareDetail expense={self.expense_id!r} "
            f"{self.origin}→{self.destination} class={self.travel_class!r}>"
        )
