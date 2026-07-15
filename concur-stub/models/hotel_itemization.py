"""
models/hotel_itemization.py
----------------------------
SQLAlchemy ORM model for the `hotel_itemization_lines` table.

Each row represents one night of a hotel stay.
The parent hotel expense holds the total amount; child lines hold
per-night breakdowns. The policy engine checks room_rate per line
against the NIGHTLY_LIMIT rule.

ITEMIZATION_SUM_MISMATCH warning is raised if:
    sum(line.line_total for line in lines) ≠ parent.amount (within ±1 INR).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class HotelItemizationLine(Base):
    __tablename__ = "hotel_itemization_lines"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    expense_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    night_date: Mapped[date] = mapped_column(Date, nullable=False)
    """The calendar date of this overnight stay."""

    room_rate: Mapped[float] = mapped_column(Float, nullable=False)
    """Nightly room charge before taxes. Validated against NIGHTLY_LIMIT."""

    taxes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    incidentals: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    line_total: Mapped[float] = mapped_column(Float, nullable=False)
    """Computed: room_rate + taxes + incidentals. Stored for fast summation."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship
    expense: Mapped["Expense"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Expense", back_populates="hotel_itemization_lines"
    )

    def __repr__(self) -> str:
        return (
            f"<HotelItemizationLine expense={self.expense_id!r} "
            f"night={self.night_date} room_rate={self.room_rate} total={self.line_total}>"
        )
