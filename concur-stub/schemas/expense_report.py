"""
schemas/expense_report.py
--------------------------
Pydantic v2 schemas for the ExpenseReport domain.

Lifecycle:
  POST /api/v4/expense-reports          → ExpenseReportCreate → ExpenseReportResponse
  GET  /api/v4/expense-reports/{id}     →                      ExpenseReportDetail
  PATCH /api/v4/expense-reports/{id}/submit  → StatusResponse (from common)
  PATCH /api/v4/expense-reports/{id}/approve → StatusResponse
  PATCH /api/v4/expense-reports/{id}/reject  → StatusResponse

The shell report is created first with mandatory fields only.
Expenses are bulk-submitted separately via the expenses router.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import ReportStatus, ValidationWarning


class ExpenseReportCreate(BaseModel):
    """
    Request body for creating a new expense report shell.
    Contains only the four mandatory fields the employee enters
    before uploading receipts.
    """
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(
        ...,
        alias="reportId",
        description="Client-supplied report ID. Must be unique per employee.",
        examples=["RPT001"],
    )
    employee_id: str = Field(
        ...,
        alias="employeeId",
        description="ID of the employee creating the report",
        examples=["EMP001"],
    )
    report_name: str = Field(
        ...,
        alias="reportName",
        description="Human-readable report name",
        examples=["Bengaluru Trip July 2026"],
    )
    business_purpose: str = Field(
        ...,
        alias="businessPurpose",
        description="Business justification for this expense report",
        examples=["Client workshop — IBM Garage"],
    )
    travel_policy: str = Field(
        ...,
        alias="travelPolicy",
        description="Travel policy name to apply (must match a seeded policy)",
        examples=["STANDARD"],
    )
    expense_category: str = Field(
        ...,
        alias="expenseCategory",
        description="Top-level expense category for the report",
        examples=["TRAVEL"],
    )
    currency: str = Field(
        default="INR",
        description="Reporting currency for this report",
        examples=["INR"],
    )


class ExpenseReportResponse(BaseModel):
    """
    Response returned after creating a new expense report shell.
    Matches SAP Concur's report creation acknowledgement shape.
    """
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(..., alias="reportId")
    status: ReportStatus
    warnings: list[ValidationWarning] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ExpenseReportDetail(BaseModel):
    """
    Full report detail including all expenses.
    Returned by GET /api/v4/expense-reports/{id}.
    """
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(..., alias="reportId")
    employee_id: str = Field(..., alias="employeeId")
    trip_id: Optional[str] = Field(default=None, alias="tripId")
    report_name: str = Field(..., alias="reportName")
    business_purpose: str = Field(..., alias="businessPurpose")
    travel_policy_name: str = Field(..., alias="travelPolicyName")
    expense_category: str = Field(..., alias="expenseCategory")
    status: ReportStatus
    total_amount: float = Field(..., alias="totalAmount")
    currency: str
    submitted_at: Optional[datetime] = Field(default=None, alias="submittedAt")
    created_at: datetime = Field(..., alias="createdAt")
    expenses: list[dict] = Field(
        default_factory=list,
        description="Expense lines belonging to this report (lightweight summary)",
    )
    warnings: list[ValidationWarning] = Field(default_factory=list)
