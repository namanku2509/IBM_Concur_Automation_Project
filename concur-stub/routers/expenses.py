"""
routers/expenses.py
--------------------
POST /api/v4/expense-reports/{reportId}/expenses

This is the primary endpoint of the stub — it triggers the full
9-step validation pipeline in expense_service.process_expenses().
The route handler is intentionally thin: receive → validate → delegate.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.expense import ExpensesSubmitRequest
from schemas.common import ExpensesSubmitResponse
from services.expense_service import process_expenses

router = APIRouter(tags=["expenses"])


@router.post(
    "/expense-reports/{report_id}/expenses",
    response_model=ExpensesSubmitResponse,
    summary="Bulk submit expenses for a report",
    description=(
        "Submits all extracted expenses for an expense report through the "
        "9-step validation pipeline. "
        "Returns a structured response with per-expense processing results, "
        "warnings, and a final report status. "
        "Pre-flight failures (invalid employee, invalid report, unsupported "
        "currency, missing mandatory fields) return HTTP 4xx and abort with "
        "zero writes. Business policy violations return HTTP 200 with warnings."
    ),
    responses={
        200: {"description": "All expenses processed. Report saved with DRAFT or MANUAL_REVIEW status."},
        403: {"description": "Employee not found or not authorized"},
        404: {"description": "Employee or report not found"},
        409: {"description": "Report is not in an editable state"},
        422: {"description": "Pre-flight validation failed (invalid type, currency, or missing fields)"},
    },
)
def submit_expenses(
    report_id: str,
    request: ExpensesSubmitRequest,
    db: Session = Depends(get_db),
) -> ExpensesSubmitResponse:
    """
    The main expense submission endpoint.
    Delegates entirely to expense_service.process_expenses().
    No business logic lives in this handler.
    """
    return process_expenses(
        report_id=report_id,
        request=request,
        db=db,
    )
