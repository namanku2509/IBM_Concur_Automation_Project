"""
repositories/expense_report_repo.py
-------------------------------------
Database access layer for the ExpenseReport domain.

Includes status transition enforcement — the only place where the
report lifecycle rules are checked.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.expense_report import ExpenseReport

# Valid status transitions (from → set of allowed to values)
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT":         {"MANUAL_REVIEW", "SUBMITTED"},
    "MANUAL_REVIEW": {"DRAFT", "SUBMITTED"},
    "SUBMITTED":     {"APPROVED", "REJECTED"},
    "APPROVED":      set(),   # terminal
    "REJECTED":      set(),   # terminal
}

# Statuses that allow expense edits (bulk submit)
EDITABLE_STATUSES = {"DRAFT", "MANUAL_REVIEW"}


def get_by_id(report_id: str, db: Session) -> ExpenseReport | None:
    return db.get(ExpenseReport, report_id)


def create(report: ExpenseReport, db: Session) -> ExpenseReport:
    db.add(report)
    db.flush()
    return report


def update_status(
    report_id: str,
    new_status: str,
    db: Session,
) -> tuple[bool, str]:
    """
    Transition an expense report to a new status.

    Returns (success: bool, message: str).
    Fails if the transition is not permitted by the lifecycle rules.
    """
    report = db.get(ExpenseReport, report_id)
    if not report:
        return False, f"Report {report_id!r} not found"

    allowed = _ALLOWED_TRANSITIONS.get(report.status, set())
    if new_status not in allowed:
        return (
            False,
            f"Cannot transition report from {report.status!r} to {new_status!r}. "
            f"Allowed next states: {sorted(allowed) or 'none (terminal state)'}",
        )

    report.status = new_status
    if new_status == "SUBMITTED":
        report.submitted_at = datetime.now(timezone.utc)
    db.flush()
    return True, f"Report {report_id!r} transitioned to {new_status!r}"


def bind_trip(report_id: str, trip_id: str, db: Session) -> None:
    """Associate the report with a matched trip."""
    report = db.get(ExpenseReport, report_id)
    if report:
        report.trip_id = trip_id
        db.flush()


def update_total(report_id: str, db: Session) -> float:
    """
    Recalculate and persist the report's total_amount from all
    top-level (non-itemization-child) expense rows.
    Returns the new total.
    """
    from models.expense import Expense
    total: float = (
        db.query(Expense)
        .filter(
            Expense.report_id == report_id,
            Expense.parent_expense_id.is_(None),
        )
        .with_entities(Expense.amount)
        .all()
    )
    # with_entities returns list of Row tuples
    total_sum = sum(row[0] for row in total)

    report = db.get(ExpenseReport, report_id)
    if report:
        report.total_amount = total_sum
        db.flush()

    return total_sum


def get_all(db: Session) -> list[ExpenseReport]:
    """Return all reports, most recently created first."""
    return (
        db.query(ExpenseReport)
        .order_by(ExpenseReport.created_at.desc())
        .all()
    )


def is_editable(report: ExpenseReport) -> bool:
    """True if the report can accept new expense submissions."""
    return report.status in EDITABLE_STATUSES
