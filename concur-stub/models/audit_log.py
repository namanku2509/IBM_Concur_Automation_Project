"""
models/audit_log.py
-------------------
SQLAlchemy ORM model for the `audit_logs` table.

Every significant business action in the stub is recorded here.
The audit log is append-only — rows are never updated or deleted.

Event types written by the system (see plan — Audit Events table):
  REPORT_CREATED, REPORT_OPENED, EXPENSES_ADDED,
  TRIP_MATCHED, TRIP_NOT_MATCHED,
  DUPLICATE_DETECTED,
  POLICY_VALIDATION_COMPLETED,
  CARD_MATCHED, CARD_NOT_MATCHED,
  REPORT_SUBMITTED, REPORT_STATUS_CHANGED

The `metadata` column holds a JSON-serialized dict with additional
context specific to each event type (e.g. warning counts, expense IDs).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    """
    The type of business event, e.g. 'REPORT_CREATED', 'TRIP_MATCHED'.
    Indexed for fast filtering by event type in the admin dashboard.
    """

    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    """The domain object this event relates to, e.g. 'expense_report', 'expense'."""

    entity_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    """The primary key of the affected entity."""

    employee_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    """Human-readable summary of the event, suitable for display in the admin dashboard."""

    event_metadata: Mapped[Optional[str]] = mapped_column(
        Text,
        name="metadata",
        nullable=True,
    )
    """
    JSON-serialized dict with event-specific context.
    Column named 'metadata' in the DB; aliased in Python to avoid conflict
    with SQLAlchemy's internal metadata attribute.
    Examples:
      {"expenseCount": 3, "warningCount": 1, "finalStatus": "DRAFT"}
      {"matchedCardId": "CCT002", "vendor": "Marriott"}
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Optional relationship to employee (nullable)
    employee: Mapped["Employee | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Employee",
        foreign_keys=[employee_id],
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} event={self.event_type!r} "
            f"entity={self.entity_type!r}:{self.entity_id!r}>"
        )
