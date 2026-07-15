"""
repositories/audit_log_repo.py
--------------------------------
Database access layer for the AuditLog domain.

The audit log is append-only — no updates or deletes.
All writes go through audit_service.py, which calls create() here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def create(log_entry: AuditLog, db: Session) -> AuditLog:
    """Append a new audit log entry. Always flushes to assign the auto-increment ID."""
    db.add(log_entry)
    db.flush()
    return log_entry


def get_recent(limit: int = 50, db: Session = None) -> list[AuditLog]:
    """Return the most recent audit log entries, newest first."""
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_for_entity(
    entity_type: str,
    entity_id: str,
    db: Session,
) -> list[AuditLog]:
    """
    Return all audit log entries for a specific entity (e.g. a report or expense).
    Used in the admin report detail view.
    """
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        .order_by(AuditLog.created_at.asc())
        .all()
    )


def get_for_employee(
    employee_id: str,
    db: Session,
    limit: int = 100,
) -> list[AuditLog]:
    """Return recent audit entries for a specific employee."""
    return (
        db.query(AuditLog)
        .filter(AuditLog.employee_id == employee_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def get_paginated(
    page: int,
    page_size: int,
    db: Session,
) -> tuple[list[AuditLog], int]:
    """
    Return a page of audit log entries and the total count.
    Used for the paginated /admin/audit-log dashboard view.
    """
    total = db.query(AuditLog).count()
    entries = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return entries, total
