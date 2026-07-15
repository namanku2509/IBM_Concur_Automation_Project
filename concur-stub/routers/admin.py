"""
routers/admin.py
-----------------
Jinja2-rendered admin dashboard routes.

/admin                  — Summary dashboard
/admin/reports          — All expense reports with status badges
/admin/reports/{id}     — Full report detail with audit trail
/admin/employees        — Employee list with travel policy column
/admin/card-transactions — All card transactions with match status
/admin/audit-log        — Paginated audit event log

These routes serve HTML for human inspection during demos.
They are NOT part of the SAP Concur API contract and are never
called by the AI Middleware (Layer 2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from repositories import (
    audit_log_repo,
    card_transaction_repo,
    employee_repo,
    expense_report_repo,
    expense_repo,
)
from models.expense_report import ExpenseReport
from models.audit_log import AuditLog

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse, summary="Admin dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    reports = expense_report_repo.get_all(db)
    status_counts = {}
    for r in reports:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    all_employees = employee_repo.get_all(db)
    recent_audit = audit_log_repo.get_recent(limit=10, db=db)

    total_expenses = sum(
        len(expense_repo.get_for_report(r.id, db)) for r in reports
    )

    return templates.TemplateResponse("dashboard.html", {
        "request":       request,
        "reports":       reports,
        "status_counts": status_counts,
        "total_reports": len(reports),
        "total_employees": len(all_employees),
        "total_expenses": total_expenses,
        "recent_audit":  recent_audit,
    })


@router.get("/reports", response_class=HTMLResponse, summary="All expense reports")
def list_reports(request: Request, db: Session = Depends(get_db)):
    reports = expense_report_repo.get_all(db)
    return templates.TemplateResponse("reports.html", {
        "request": request,
        "reports": reports,
    })


@router.get("/reports/{report_id}", response_class=HTMLResponse, summary="Report detail")
def report_detail(report_id: str, request: Request, db: Session = Depends(get_db)):
    report = expense_report_repo.get_by_id(report_id, db)
    if not report:
        return HTMLResponse(content=f"<h1>Report {report_id!r} not found</h1>", status_code=404)

    expenses = expense_repo.get_for_report(report_id, db)
    audit_entries = audit_log_repo.get_for_entity("expense_report", report_id, db)

    return templates.TemplateResponse("report_detail.html", {
        "request":       request,
        "report":        report,
        "expenses":      expenses,
        "audit_entries": audit_entries,
    })


@router.get("/employees", response_class=HTMLResponse, summary="All employees")
def list_employees(request: Request, db: Session = Depends(get_db)):
    employees = employee_repo.get_all(db)
    return templates.TemplateResponse("employees.html", {
        "request":   request,
        "employees": employees,
    })


@router.get("/card-transactions", response_class=HTMLResponse, summary="All card transactions")
def list_card_transactions(request: Request, db: Session = Depends(get_db)):
    txns = card_transaction_repo.get_all(db)
    return templates.TemplateResponse("card_transactions.html", {
        "request": request,
        "txns":    txns,
    })


@router.get("/audit-log", response_class=HTMLResponse, summary="Audit event log")
def audit_log(
    request:   Request,
    page:      int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=100),
    db: Session = Depends(get_db),
):
    entries, total = audit_log_repo.get_paginated(page, page_size, db)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return templates.TemplateResponse("audit_log.html", {
        "request":     request,
        "entries":     entries,
        "page":        page,
        "page_size":   page_size,
        "total":       total,
        "total_pages": total_pages,
    })
