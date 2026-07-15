"""
routers/expense_reports.py
---------------------------
POST  /api/v4/expense-reports               — Create shell report
GET   /api/v4/expense-reports/{id}          — Fetch full report detail
PATCH /api/v4/expense-reports/{id}/submit   — Employee submits report
PATCH /api/v4/expense-reports/{id}/approve  — Manager approves (admin)
PATCH /api/v4/expense-reports/{id}/reject   — Manager rejects (admin)
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.expense_report import ExpenseReport
from repositories import employee_repo, expense_repo, expense_report_repo
from schemas.common import ErrorCode, ErrorResponse, ReportStatus, StatusResponse
from schemas.expense_report import (
    ExpenseReportCreate,
    ExpenseReportDetail,
    ExpenseReportResponse,
)
from services import audit_service
from services.audit_service import AuditEntity, AuditEvent

router = APIRouter(tags=["expense-reports"])


# ------------------------------------------------------------------ #
# POST — Create shell report                                           #
# ------------------------------------------------------------------ #

@router.post(
    "/expense-reports",
    response_model=ExpenseReportResponse,
    status_code=201,
    summary="Create a new expense report (shell)",
    description=(
        "Creates an empty expense report container with the four mandatory "
        "fields. Expenses are added separately via POST /expense-reports/{id}/expenses."
    ),
)
def create_expense_report(
    payload: ExpenseReportCreate,
    db: Session = Depends(get_db),
) -> ExpenseReportResponse:
    # Validate employee
    emp = employee_repo.get_by_id(payload.employee_id, db)
    if not emp:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {payload.employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    if not emp.is_active:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_INACTIVE,
                message=f"Employee {payload.employee_id!r} is inactive.",
            ).model_dump(by_alias=True),
        )

    # Check for duplicate report ID up front — gives a clean 409
    if expense_report_repo.get_by_id(payload.report_id, db):
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                code=ErrorCode.INVALID_STATUS_TRANSITION,
                message=f"Report ID {payload.report_id!r} already exists. "
                        f"Use a different reportId or fetch the existing report.",
            ).model_dump(by_alias=True),
        )

    report = ExpenseReport(
        id=payload.report_id,
        employee_id=payload.employee_id,
        report_name=payload.report_name,
        business_purpose=payload.business_purpose,
        travel_policy_name=emp.travel_policy_name,
        expense_category=payload.expense_category,
        status="DRAFT",
        total_amount=0.0,
        currency=payload.currency,
    )
    try:
        expense_report_repo.create(report, db)
        audit_service.log_event(
            event_type=AuditEvent.REPORT_CREATED,
            entity_type=AuditEntity.EXPENSE_REPORT,
            entity_id=payload.report_id,
            employee_id=payload.employee_id,
            description=f"Report {payload.report_id!r} created: {payload.report_name!r}.",
            db=db,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                code=ErrorCode.INVALID_STATUS_TRANSITION,
                message=f"Report ID {payload.report_id!r} already exists.",
            ).model_dump(by_alias=True),
        )

    return ExpenseReportResponse(
        report_id=report.id,
        status=ReportStatus.DRAFT,
        warnings=[],
        errors=[],
    )


# ------------------------------------------------------------------ #
# GET — Full report detail                                             #
# ------------------------------------------------------------------ #

@router.get(
    "/expense-reports/{report_id}",
    response_model=ExpenseReportDetail,
    summary="Get expense report with all expenses",
    responses={404: {"model": ErrorResponse}},
)
def get_expense_report(
    report_id: str,
    db: Session = Depends(get_db),
) -> ExpenseReportDetail:
    report = expense_report_repo.get_by_id(report_id, db)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_FOUND,
                message=f"Report {report_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )

    expenses = expense_repo.get_for_report(report_id, db)

    return ExpenseReportDetail(
        report_id=report.id,
        employee_id=report.employee_id,
        trip_id=report.trip_id,
        report_name=report.report_name,
        business_purpose=report.business_purpose,
        travel_policy_name=report.travel_policy_name,
        expense_category=report.expense_category,
        status=ReportStatus(report.status),
        total_amount=report.total_amount,
        currency=report.currency,
        submitted_at=report.submitted_at,
        created_at=report.created_at,
        expenses=[
            {
                "expenseId": e.id,
                "expenseType": e.expense_type,
                "vendor": e.vendor,
                "amount": e.amount,
                "currency": e.currency,
                "transactionDate": str(e.transaction_date),
                "status": e.status,
            }
            for e in expenses
        ],
    )


# ------------------------------------------------------------------ #
# PATCH — Lifecycle transitions                                        #
# ------------------------------------------------------------------ #

def _transition_report(
    report_id: str,
    new_status: str,
    db: Session,
    audit_event: str,
    audit_description: str,
) -> StatusResponse:
    report = expense_report_repo.get_by_id(report_id, db)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_FOUND,
                message=f"Report {report_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )

    success, msg = expense_report_repo.update_status(report_id, new_status, db)
    if not success:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                code=ErrorCode.INVALID_STATUS_TRANSITION,
                message=msg,
            ).model_dump(by_alias=True),
        )

    audit_service.log_event(
        event_type=audit_event,
        entity_type=AuditEntity.EXPENSE_REPORT,
        entity_id=report_id,
        employee_id=report.employee_id,
        description=audit_description,
        db=db,
        metadata_dict={"newStatus": new_status},
    )
    db.commit()

    return StatusResponse(
        report_id=report_id,
        status=ReportStatus(new_status),
        message=msg,
    )


@router.patch(
    "/expense-reports/{report_id}/submit",
    response_model=StatusResponse,
    summary="Submit expense report for approval",
)
def submit_report(report_id: str, db: Session = Depends(get_db)) -> StatusResponse:
    """Transition the report from DRAFT or MANUAL_REVIEW → SUBMITTED."""
    return _transition_report(
        report_id=report_id,
        new_status="SUBMITTED",
        db=db,
        audit_event=AuditEvent.REPORT_SUBMITTED,
        audit_description=f"Report {report_id!r} submitted for manager approval.",
    )


@router.patch(
    "/expense-reports/{report_id}/approve",
    response_model=StatusResponse,
    summary="Approve a submitted expense report (manager/admin)",
)
def approve_report(report_id: str, db: Session = Depends(get_db)) -> StatusResponse:
    """Transition SUBMITTED → APPROVED. Admin/manager endpoint."""
    return _transition_report(
        report_id=report_id,
        new_status="APPROVED",
        db=db,
        audit_event=AuditEvent.REPORT_STATUS_CHANGED,
        audit_description=f"Report {report_id!r} approved.",
    )


@router.patch(
    "/expense-reports/{report_id}/reject",
    response_model=StatusResponse,
    summary="Reject a submitted expense report (manager/admin)",
)
def reject_report(report_id: str, db: Session = Depends(get_db)) -> StatusResponse:
    """Transition SUBMITTED → REJECTED. Admin/manager endpoint."""
    return _transition_report(
        report_id=report_id,
        new_status="REJECTED",
        db=db,
        audit_event=AuditEvent.REPORT_STATUS_CHANGED,
        audit_description=f"Report {report_id!r} rejected.",
    )
