"""
models/receipt.py
-----------------
SQLAlchemy ORM model for the `receipts` table.

The stub never stores raw receipt images or PDFs.
Layer 2 (AI Middleware) retains all binary assets.

The stub records only:
  - A receipt reference ID returned to Layer 2 after registration
  - The SHA-256 hash used for duplicate detection
  - Optional metadata (filename, mime type, OCR confidence) for display

Duplicate detection (Step 6 of the pipeline) queries this table
by receipt_hash + employee_id combination.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    receipt_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    """
    SHA-256 of vendor.lower() + ':' + str(amount) + ':' + transactionDate + ':' + employee_id.
    Indexed for fast duplicate detection queries.
    """

    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    """Confidence score (0.0–1.0) from Layer 2's OCR engine. Used by OcrConfidenceValidator."""

    registered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    employee: Mapped["Employee"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Employee", back_populates="receipts"
    )
    expense: Mapped["Expense | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Expense",
        back_populates="receipt",
        foreign_keys="Expense.receipt_id",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Receipt id={self.id!r} employee={self.employee_id!r} hash={self.receipt_hash[:12]}...>"
