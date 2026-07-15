"""
models/meal_detail.py
---------------------
SQLAlchemy ORM model for the `meal_details` table.

One-to-one with an expense of type MEAL.
meal_type and attendees provide context for policy validation
(e.g. per-head meal limits could be derived from amount / attendees).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MealDetail(Base):
    __tablename__ = "meal_details"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    expense_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    meal_type: Mapped[str] = mapped_column(String, nullable=False, default="MEAL")
    """Valid values: BREAKFAST | LUNCH | DINNER | SNACK | MEAL"""

    attendees: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship
    expense: Mapped["Expense"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Expense", back_populates="meal_detail"
    )

    def __repr__(self) -> str:
        return (
            f"<MealDetail expense={self.expense_id!r} "
            f"type={self.meal_type!r} attendees={self.attendees}>"
        )
