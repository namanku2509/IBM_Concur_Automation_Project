"""
models/taxi_detail.py
---------------------
SQLAlchemy ORM model for the `taxi_details` table.

One-to-one with an expense of type TAXI.
from_location and to_location provide trip context.
distance_km is optional — populated when available from the OCR output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TaxiDetail(Base):
    __tablename__ = "taxi_details"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    expense_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    from_location: Mapped[str] = mapped_column(String, nullable=False)
    to_location: Mapped[str] = mapped_column(String, nullable=False)
    distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship
    expense: Mapped["Expense"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Expense", back_populates="taxi_detail"
    )

    def __repr__(self) -> str:
        return (
            f"<TaxiDetail expense={self.expense_id!r} "
            f"{self.from_location!r}→{self.to_location!r}>"
        )
