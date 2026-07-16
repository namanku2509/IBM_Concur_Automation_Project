"""
schemas/common.py
-----------------
Shared envelope types used across all API responses.

These models define the Concur-style response structure that Layer 2
(AI Middleware / Orchestrate Skills) receives from every endpoint.

Design principles:
- All response envelopes use camelCase field names via `alias` to mirror
  SAP Concur v4 API conventions.
- `populate_by_name=True` allows internal Python code to use snake_case
  while the serialized JSON output uses camelCase aliases.
- `by_alias=True` must be passed to `.model_dump()` / `.model_json_schema()`
  when serializing for external consumption.

Warning/Error taxonomy (from the plan):
  ValidationWarning — business policy issues; report is still saved
  PreflightError    — structural issues; entire request is aborted
  ProcessedExpense  — per-expense result within a bulk submit response
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------ #
# Enumerations                                                         #
# ------------------------------------------------------------------ #

class WarningSeverity(str, Enum):
    WARNING = "WARNING"
    INFO    = "INFO"


class ExpenseStatus(str, Enum):
    MATCHED       = "MATCHED"
    PENDING       = "PENDING"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ReportStatus(str, Enum):
    DRAFT         = "DRAFT"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    SUBMITTED     = "SUBMITTED"
    APPROVED      = "APPROVED"
    REJECTED      = "REJECTED"


class ExpenseType(str, Enum):
    HOTEL  = "HOTEL"
    MEAL   = "MEAL"
    TAXI   = "TAXI"
    FLIGHT = "FLIGHT"


class PaymentType(str, Enum):
    CORPORATE_CARD  = "CORPORATE_CARD"
    PERSONAL_CASH   = "PERSONAL_CASH"
    CORPORATE_CASH  = "CORPORATE_CASH"


class TravelClass(str, Enum):
    ECONOMY  = "ECONOMY"
    BUSINESS = "BUSINESS"


class MealType(str, Enum):
    BREAKFAST = "BREAKFAST"
    LUNCH     = "LUNCH"
    DINNER    = "DINNER"
    SNACK     = "SNACK"
    MEAL      = "MEAL"


class TripStatus(str, Enum):
    PLANNED   = "PLANNED"
    ACTIVE    = "ACTIVE"
    COMPLETED = "COMPLETED"


class CardTxnStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MATCHED   = "MATCHED"
    IGNORED   = "IGNORED"


# ------------------------------------------------------------------ #
# Warning codes                                                        #
# ------------------------------------------------------------------ #

class WarningCode(str, Enum):
    TRIP_NOT_MATCHED            = "TRIP_NOT_MATCHED"
    DUPLICATE_RECEIPT_DETECTED  = "DUPLICATE_RECEIPT_DETECTED"
    HOTEL_NIGHTLY_LIMIT_EXCEEDED = "HOTEL_NIGHTLY_LIMIT_EXCEEDED"
    MEAL_LIMIT_EXCEEDED         = "MEAL_LIMIT_EXCEEDED"
    CARD_TRANSACTION_NOT_MATCHED = "CARD_TRANSACTION_NOT_MATCHED"
    CARD_ALREADY_MATCHED        = "CARD_ALREADY_MATCHED"
    PAYMENT_TYPE_ADVISORY       = "PAYMENT_TYPE_ADVISORY"
    TRAVEL_CLASS_VIOLATION      = "TRAVEL_CLASS_VIOLATION"
    ITEMIZATION_SUM_MISMATCH    = "ITEMIZATION_SUM_MISMATCH"
    LOW_OCR_CONFIDENCE          = "LOW_OCR_CONFIDENCE"


# ------------------------------------------------------------------ #
# Pre-flight error codes                                               #
# ------------------------------------------------------------------ #

class ErrorCode(str, Enum):
    EMPLOYEE_NOT_FOUND          = "EMPLOYEE_NOT_FOUND"
    EMPLOYEE_INACTIVE           = "EMPLOYEE_INACTIVE"
    REPORT_NOT_FOUND            = "REPORT_NOT_FOUND"
    REPORT_NOT_EDITABLE         = "REPORT_NOT_EDITABLE"
    UNAUTHORIZED                = "UNAUTHORIZED"
    INVALID_EXPENSE_TYPE        = "INVALID_EXPENSE_TYPE"
    INVALID_CURRENCY            = "INVALID_CURRENCY"
    MISSING_REQUIRED_FIELD      = "MISSING_REQUIRED_FIELD"
    ITEMIZATION_REQUIRED        = "ITEMIZATION_REQUIRED"
    AIRFARE_DETAIL_REQUIRED     = "AIRFARE_DETAIL_REQUIRED"
    INVALID_STATUS_TRANSITION   = "INVALID_STATUS_TRANSITION"
    DUPLICATE_RECEIPT           = "DUPLICATE_RECEIPT"


# ------------------------------------------------------------------ #
# Core message types                                                   #
# ------------------------------------------------------------------ #

class ValidationWarning(BaseModel):
    """
    A non-blocking business policy warning.
    Accumulates in expense or report level warnings[].
    Processing always continues; the report is saved.
    """
    model_config = ConfigDict(populate_by_name=True)

    code: WarningCode = Field(
        ...,
        description="Machine-readable warning code",
        examples=["HOTEL_NIGHTLY_LIMIT_EXCEEDED"],
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the warning",
        examples=["Nightly room rate ₹7500 exceeds policy limit ₹6000 for STANDARD policy"],
    )
    severity: WarningSeverity = Field(
        default=WarningSeverity.WARNING,
        description="Severity level of this warning",
    )
    field: Optional[str] = Field(
        default=None,
        description="The specific field that triggered this warning, if applicable",
        examples=["roomRate"],
    )


class PreflightError(BaseModel):
    """
    A structural validation error detected during pre-flight (Step 3).
    These are returned in the HTTP 422 response body when the whole
    request is aborted before any DB writes.
    """
    model_config = ConfigDict(populate_by_name=True)

    code: ErrorCode = Field(
        ...,
        description="Machine-readable error code",
        examples=["MISSING_REQUIRED_FIELD"],
    )
    message: str = Field(
        ...,
        description="Human-readable explanation",
        examples=["Field 'vendor' is required and must be a non-empty string"],
    )
    field: Optional[str] = Field(
        default=None,
        description="The field that failed validation",
        examples=["vendor"],
    )
    expense_index: Optional[int] = Field(
        default=None,
        alias="expenseIndex",
        description="Zero-based index of the expense in the submitted array that failed",
        examples=[0],
    )


class PreflightErrorResponse(BaseModel):
    """
    HTTP 422 response body when pre-flight validation fails.
    All errors across all expenses are collected and returned together
    so the caller can fix everything in a single round trip.
    """
    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(default="PREFLIGHT_FAILED")
    errors: list[PreflightError] = Field(
        default_factory=list,
        description="All pre-flight validation failures",
    )


# ------------------------------------------------------------------ #
# Per-expense result (bulk submit response)                           #
# ------------------------------------------------------------------ #

class ProcessedExpense(BaseModel):
    """
    The result of processing a single expense through the 9-step pipeline.
    One of these is returned for every expense in the bulk submit response.
    """
    model_config = ConfigDict(populate_by_name=True)

    expense_id: str = Field(
        ...,
        alias="expenseId",
        description="Generated ID for the persisted expense",
        examples=["EXP001"],
    )
    vendor: str = Field(..., description="Vendor name as submitted")
    expense_type: ExpenseType = Field(..., alias="expenseType")
    amount: float = Field(..., description="Expense amount")
    currency: str = Field(..., description="Currency code")
    status: ExpenseStatus = Field(
        ...,
        description="Final status of this expense after pipeline processing",
    )
    card_transaction_id: Optional[str] = Field(
        default=None,
        alias="cardTransactionId",
        description="ID of the matched corporate card transaction, if any",
    )
    receipt_id: Optional[str] = Field(
        default=None,
        alias="receiptId",
        description="ID of the linked receipt, if provided",
    )
    warnings: list[ValidationWarning] = Field(
        default_factory=list,
        description="Business policy warnings for this specific expense",
    )


# ------------------------------------------------------------------ #
# Bulk submit response envelope                                        #
# ------------------------------------------------------------------ #

class SubmitSummary(BaseModel):
    """Aggregated counts from a bulk expense submission."""
    model_config = ConfigDict(populate_by_name=True)

    total_expenses: int = Field(..., alias="totalExpenses")
    total_amount: float = Field(..., alias="totalAmount")
    currency: str
    matched_count: int = Field(..., alias="matchedCount")
    pending_count: int = Field(..., alias="pendingCount")
    manual_review_count: int = Field(..., alias="manualReviewCount")
    warning_count: int = Field(..., alias="warningCount")


class ExpensesSubmitResponse(BaseModel):
    """
    Response envelope returned by POST /api/v4/expense-reports/{id}/expenses.
    Mirrors SAP Concur's expense submission acknowledgement structure.
    """
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(..., alias="reportId")
    status: ReportStatus = Field(
        ...,
        description="Final report status after processing all expenses",
    )
    warnings: list[ValidationWarning] = Field(
        default_factory=list,
        description="Report-level warnings (e.g. TRIP_NOT_MATCHED)",
    )
    processed_expenses: list[ProcessedExpense] = Field(
        ...,
        alias="processedExpenses",
        description="Per-expense processing results",
    )
    summary: SubmitSummary = Field(
        ...,
        description="Aggregated totals and counts",
    )


# ------------------------------------------------------------------ #
# Generic success response (for simple operations)                    #
# ------------------------------------------------------------------ #

class StatusResponse(BaseModel):
    """Simple acknowledgement used for submit/approve/reject transitions."""
    model_config = ConfigDict(populate_by_name=True)

    report_id: str = Field(..., alias="reportId")
    status: ReportStatus
    message: str = Field(..., description="Human-readable confirmation")


# ------------------------------------------------------------------ #
# Generic HTTP error response (for 4xx responses)                     #
# ------------------------------------------------------------------ #

class ErrorResponse(BaseModel):
    """
    Standard error envelope for 4xx responses (employee not found,
    report not editable, unauthorized, etc.).
    """
    model_config = ConfigDict(populate_by_name=True)

    code: ErrorCode
    message: str
    detail: Optional[Any] = Field(default=None)
