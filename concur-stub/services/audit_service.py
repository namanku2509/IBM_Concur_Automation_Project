"""
services/audit_service.py
--------------------------
Audit logging service — the single write point for all audit_logs entries.

Every significant business action in the validation pipeline calls
log_event(). Callers never interact with the audit_log_repo directly.

Design:
  - All arguments except db are plain Python types (strings, dicts)
    so callers have no schema imports required.
  - metadata_dict is serialized to JSON here — callers pass plain dicts.
  - Failures are caught and logged — audit writes must never cause a
    business operation to fail.

Event type constants are defined at the bottom of this file as a
convenience import for service-layer callers.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from repositories import audit_log_repo

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Event type constants                                                 #
# ------------------------------------------------------------------ #

class AuditEvent:
    """Namespace for all audit event type string constants."""
    REPORT_CREATED               = "REPORT_CREATED"
    REPORT_OPENED                = "REPORT_OPENED"
    EXPENSES_ADDED               = "EXPENSES_ADDED"
    TRIP_MATCHED                 = "TRIP_MATCHED"
    TRIP_NOT_MATCHED             = "TRIP_NOT_MATCHED"
    DUPLICATE_DETECTED           = "DUPLICATE_DETECTED"
    POLICY_VALIDATION_COMPLETED  = "POLICY_VALIDATION_COMPLETED"
    CARD_MATCHED                 = "CARD_MATCHED"
    CARD_NOT_MATCHED             = "CARD_NOT_MATCHED"
    REPORT_SUBMITTED             = "REPORT_SUBMITTED"
    REPORT_STATUS_CHANGED        = "REPORT_STATUS_CHANGED"


# ------------------------------------------------------------------ #
# Entity type constants                                                #
# ------------------------------------------------------------------ #

class AuditEntity:
    EXPENSE_REPORT = "expense_report"
    EXPENSE        = "expense"
    TRIP           = "trip"
    RECEIPT        = "receipt"
    CARD_TXN       = "card_transaction"


# ------------------------------------------------------------------ #
# Core log_event function                                              #
# ------------------------------------------------------------------ #

def log_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    description: str,
    db: Session,
    employee_id: Optional[str] = None,
    metadata_dict: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append one audit log entry.

    Parameters:
        event_type:    One of the AuditEvent constants.
        entity_type:   One of the AuditEntity constants.
        entity_id:     Primary key of the affected entity.
        description:   Human-readable summary (shown in admin dashboard).
        db:            Active SQLAlchemy session.
        employee_id:   Optional — the acting employee (FK to employees.id).
        metadata_dict: Optional dict serialized to JSON for storage.

    Failures are caught silently — audit writes must never abort a
    business operation. A warning is logged to the application log instead.
    """
    try:
        metadata_json: Optional[str] = None
        if metadata_dict:
            metadata_json = json.dumps(metadata_dict, default=str)

        entry = AuditLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            employee_id=employee_id,
            description=description,
            event_metadata=metadata_json,
            created_at=datetime.now(timezone.utc),
        )
        audit_log_repo.create(entry, db)

    except Exception:
        logger.exception(
            "Failed to write audit log entry: event=%s entity=%s:%s",
            event_type,
            entity_type,
            entity_id,
        )
