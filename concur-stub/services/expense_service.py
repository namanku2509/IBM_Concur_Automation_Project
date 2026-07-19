"""
services/expense_service.py
----------------------------
Core 9-step expense validation pipeline.

This is the central orchestrator of the SAP Concur Stub. It is the only
place where all validation steps are coordinated. Route handlers call
process_expenses() and receive the full Concur-style response.

Pipeline overview (from the design plan):

  Steps 1–3  [PRE-FLIGHT]  — Validate before any DB writes.
                             On failure: raise HTTPException → abort.
  Steps 4–9  [WRITE PHASE] — Write data; accumulate warnings.
                             On business issues: add warnings, continue.

Step 1  Employee validation          (404 / 403)
Step 2  Report validation            (404 / 409 / 403)
Step 3  Full pre-flight on all       (422 — all errors collected together)
        expenses: type, currency,
        mandatory fields
Step 4  Audit: report opened         (write audit log)
Step 5  Trip matching                (WARNING: TRIP_NOT_MATCHED)
Step 6  Duplicate detection          (WARNING: DUPLICATE_RECEIPT_DETECTED)
Step 7  Policy validation            (WARNINGs from policy engine)
Step 8  Card transaction matching    (WARNING: CARD_TRANSACTION_NOT_MATCHED)
Step 9  Persist & respond            (write all DB rows, return response)
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import settings
from models.expense import Expense
from models.hotel_itemization import HotelItemizationLine
from models.airfare_detail import AirfareDetail
from models.taxi_detail import TaxiDetail
from models.meal_detail import MealDetail
from models.receipt import Receipt
from repositories import (
    card_transaction_repo,
    employee_repo,
    expense_repo,
    expense_report_repo,
    receipt_repo,
)
from schemas.common import (
    ErrorCode,
    ErrorResponse,
    ExpenseStatus,
    ExpensesSubmitResponse,
    PreflightError,
    PreflightErrorResponse,
    ProcessedExpense,
    ReportStatus,
    SubmitSummary,
    ValidationWarning,
    WarningCode,
    WarningSeverity,
)
from schemas.expense import ExpenseInput, ExpensesSubmitRequest
from services import audit_service, duplicate_detection, policy_engine, trip_matching_service
from services.audit_service import AuditEntity, AuditEvent


# ------------------------------------------------------------------ #
# Supported currencies (loaded from policy_rules at runtime)          #
# For pre-flight validation we query the DB; this constant is the     #
# fallback if no policy rows exist yet.                               #
# ------------------------------------------------------------------ #
_FALLBACK_SUPPORTED_CURRENCIES = {"INR", "USD", "GBP", "EUR"}
_VALID_EXPENSE_TYPES = {"HOTEL", "MEAL", "TAXI", "FLIGHT"}


def _get_supported_currencies(db: Session) -> set[str]:
    """
    Collect all currencies that appear in ALLOWED_CURRENCIES policy rules.
    Returns a union across all policies so any valid currency passes pre-flight.
    """
    from models.travel_policy import PolicyRule
    import json

    rows = (
        db.query(PolicyRule)
        .filter(PolicyRule.rule_key == "ALLOWED_CURRENCIES")
        .all()
    )
    currencies: set[str] = set()
    for row in rows:
        try:
            values = json.loads(row.rule_value)
            if isinstance(values, list):
                currencies.update(str(v).upper() for v in values)
        except Exception:
            pass
    return currencies or _FALLBACK_SUPPORTED_CURRENCIES


# ------------------------------------------------------------------ #
# Public entry point                                                   #
# ------------------------------------------------------------------ #

def process_expenses(
    report_id: str,
    request: ExpensesSubmitRequest,
    db: Session,
) -> ExpensesSubmitResponse:
    """
    Execute the 9-step validation pipeline for a bulk expense submission.

    Raises HTTPException for Steps 1–3 pre-flight failures.
    Returns ExpensesSubmitResponse for Steps 4–9 (always persists).
    """
    employee_id = request.employee_id
    expenses    = request.expenses

    # ================================================================
    # STEP 1 — Employee Validation
    # ================================================================
    employee = employee_repo.get_by_id(employee_id, db)
    if employee is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    if not employee.is_active:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_INACTIVE,
                message=f"Employee {employee_id!r} account is deactivated.",
            ).model_dump(by_alias=True),
        )

    # ================================================================
    # STEP 2 — Report Validation
    # ================================================================
    report = expense_report_repo.get_by_id(report_id, db)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_FOUND,
                message=f"Expense report {report_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    if report.employee_id != employee_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                code=ErrorCode.UNAUTHORIZED,
                message="The employee ID in the request does not match the report owner.",
            ).model_dump(by_alias=True),
        )
    if not expense_report_repo.is_editable(report):
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_EDITABLE,
                message=(
                    f"Report {report_id!r} has status {report.status!r} and cannot "
                    "accept new expenses. Only DRAFT or MANUAL_REVIEW reports are editable."
                ),
            ).model_dump(by_alias=True),
        )

    # ================================================================
    # STEP 3 — Full Pre-flight Validation (all expenses, no writes)
    # ================================================================
    supported_currencies = _get_supported_currencies(db)
    preflight_errors: list[PreflightError] = []

    for idx, expense in enumerate(expenses):
        # Expense type
        if expense.expense_type.value not in _VALID_EXPENSE_TYPES:
            preflight_errors.append(PreflightError(
                code=ErrorCode.INVALID_EXPENSE_TYPE,
                message=f"Expense type {expense.expense_type.value!r} is not supported.",
                field="expenseType",
                expense_index=idx,
            ))

        # Currency
        if expense.currency.upper() not in supported_currencies:
            preflight_errors.append(PreflightError(
                code=ErrorCode.INVALID_CURRENCY,
                message=(
                    f"Currency {expense.currency!r} is not in the supported list: "
                    f"{sorted(supported_currencies)}."
                ),
                field="currency",
                expense_index=idx,
            ))

        # Mandatory fields (Pydantic already enforces min_length=1 and gt=0,
        # but we add explicit messages here for Concur-style error reporting)
        if not expense.vendor or not expense.vendor.strip():
            preflight_errors.append(PreflightError(
                code=ErrorCode.MISSING_REQUIRED_FIELD,
                message="Field 'vendor' is required and must be a non-empty string.",
                field="vendor",
                expense_index=idx,
            ))
        if expense.amount <= 0:
            preflight_errors.append(PreflightError(
                code=ErrorCode.MISSING_REQUIRED_FIELD,
                message="Field 'amount' must be a positive number greater than 0.",
                field="amount",
                expense_index=idx,
            ))

        # Type-specific mandatory sub-objects
        if expense.expense_type.value == "HOTEL":
            if not expense.itemization:
                preflight_errors.append(PreflightError(
                    code=ErrorCode.ITEMIZATION_REQUIRED,
                    message="HOTEL expenses must include an 'itemization' array with at least one night.",
                    field="itemization",
                    expense_index=idx,
                ))
        # NOTE: FLIGHT airfareDetail is intentionally NOT mandatory at pre-flight.
        # The schema has all-default values so missing OCR fields won't cause 422.
        # The BFF always sends an airfareDetail object (with UNKNOWN defaults) for FLIGHT.

    if preflight_errors:
        raise HTTPException(
            status_code=422,
            detail=PreflightErrorResponse(
                status="PREFLIGHT_FAILED",
                errors=preflight_errors,
            ).model_dump(by_alias=True),
        )

    # ================================================================
    # STEP 4 — Audit: Report Opened for Writing
    # ================================================================
    audit_service.log_event(
        event_type=AuditEvent.REPORT_OPENED,
        entity_type=AuditEntity.EXPENSE_REPORT,
        entity_id=report_id,
        employee_id=employee_id,
        description=(
            f"Expense bulk-submit started for report {report_id!r}. "
            f"{len(expenses)} expense(s) submitted."
        ),
        db=db,
        metadata_dict={"expenseCount": len(expenses)},
    )

    # ================================================================
    # STEP 5 — Trip Matching
    # ================================================================
    report_level_warnings: list[ValidationWarning] = []

    expense_dates   = [e.transaction_date for e in expenses]
    expense_cities  = [e.city for e in expenses]
    expense_vendors = [e.vendor for e in expenses]
    expense_amounts = [e.amount for e in expenses]

    matched_trip = trip_matching_service.find_matching_trip(
        employee_id=employee_id,
        expense_dates=expense_dates,
        expense_cities=expense_cities,
        db=db,
        expense_vendors=expense_vendors,
        expense_amounts=expense_amounts,
    )

    if matched_trip:
        expense_report_repo.bind_trip(report_id, matched_trip.id, db)
        audit_service.log_event(
            event_type=AuditEvent.TRIP_MATCHED,
            entity_type=AuditEntity.TRIP,
            entity_id=matched_trip.id,
            employee_id=employee_id,
            description=f"Trip {matched_trip.id!r} matched to report {report_id!r}.",
            db=db,
            metadata_dict={"tripId": matched_trip.id, "city": matched_trip.destination_city},
        )
    else:
        report_level_warnings.append(ValidationWarning(
            code=WarningCode.TRIP_NOT_MATCHED,
            message=(
                "No matching business trip was found for the submitted expenses. "
                "Please associate this report with a valid business trip before "
                "final submission."
            ),
            severity=WarningSeverity.WARNING,
        ))
        audit_service.log_event(
            event_type=AuditEvent.TRIP_NOT_MATCHED,
            entity_type=AuditEntity.EXPENSE_REPORT,
            entity_id=report_id,
            employee_id=employee_id,
            description=f"No matching trip found for report {report_id!r}.",
            db=db,
        )

    # ================================================================
    # Per-expense processing (Steps 6–8) then persist (Step 9)
    # ================================================================
    processed: list[ProcessedExpense] = []
    total_warning_count = len(report_level_warnings)
    policy_name = employee.travel_policy_name

    for expense_input in expenses:
        exp_warnings: list[ValidationWarning] = []
        expense_status = "PENDING"
        matched_card_id: Optional[str] = None

        # ============================================================
        # STEP 6 — Duplicate Detection
        # ============================================================
        tx_date_str = str(expense_input.transaction_date)
        receipt_hash = duplicate_detection.compute_receipt_hash(
            vendor=expense_input.vendor,
            amount=expense_input.amount,
            transaction_date=tx_date_str,
            employee_id=employee_id,
        )
        dup, existing_receipt_id = duplicate_detection.is_duplicate(receipt_hash, employee_id, db)

        if dup:
            exp_warnings.append(ValidationWarning(
                code=WarningCode.DUPLICATE_RECEIPT_DETECTED,
                message=(
                    f"A receipt for {expense_input.vendor!r} of "
                    f"{expense_input.currency} {expense_input.amount:,.2f} "
                    f"on {expense_input.transaction_date} has already been submitted."
                ),
                severity=WarningSeverity.WARNING,
            ))
            expense_status = "MANUAL_REVIEW"
            audit_service.log_event(
                event_type=AuditEvent.DUPLICATE_DETECTED,
                entity_type=AuditEntity.RECEIPT,
                entity_id=existing_receipt_id or "UNKNOWN",
                employee_id=employee_id,
                description=f"Duplicate receipt detected for vendor {expense_input.vendor!r}.",
                db=db,
                metadata_dict={
                    "vendor": expense_input.vendor,
                    "amount": expense_input.amount,
                    "transactionDate": tx_date_str,
                },
            )

        # ============================================================
        # STEP 7 — Policy Validation
        # ============================================================
        policy_warnings = policy_engine.run_policy_checks(expense_input, policy_name, db)
        exp_warnings.extend(policy_warnings)

        # ============================================================
        # STEP 8 — Card Transaction Matching
        # ============================================================
        if expense_input.payment_type.value == "CORPORATE_CARD":
            matched_txn = card_transaction_repo.find_matching_transaction(
                employee_id=employee_id,
                vendor=expense_input.vendor,
                amount=expense_input.amount,
                transaction_date=expense_input.transaction_date,
                db=db,
                date_tolerance_days=settings.card_match_date_tolerance_days,
            )
            if matched_txn:
                matched_card_id = matched_txn.id
                if expense_status != "MANUAL_REVIEW":
                    expense_status = "MATCHED"
                audit_service.log_event(
                    event_type=AuditEvent.CARD_MATCHED,
                    entity_type=AuditEntity.CARD_TXN,
                    entity_id=matched_txn.id,
                    employee_id=employee_id,
                    description=(
                        f"Card transaction {matched_txn.id!r} matched to "
                        f"expense for {expense_input.vendor!r}."
                    ),
                    db=db,
                    metadata_dict={
                        "cardTransactionId": matched_txn.id,
                        "vendor": expense_input.vendor,
                    },
                )
            else:
                if expense_status != "MANUAL_REVIEW":
                    expense_status = "PENDING"
                exp_warnings.append(ValidationWarning(
                    code=WarningCode.CARD_TRANSACTION_NOT_MATCHED,
                    message=(
                        f"No matching corporate card transaction found for "
                        f"{expense_input.vendor!r} "
                        f"{expense_input.currency} {expense_input.amount:,.2f} "
                        f"on or near {expense_input.transaction_date}."
                    ),
                    severity=WarningSeverity.WARNING,
                ))
                audit_service.log_event(
                    event_type=AuditEvent.CARD_NOT_MATCHED,
                    entity_type=AuditEntity.EXPENSE,
                    entity_id="PENDING",
                    employee_id=employee_id,
                    description=f"No card match for {expense_input.vendor!r}.",
                    db=db,
                )

        # ============================================================
        # STEP 9 — Persist this expense
        # ============================================================
        expense_id = f"EXP-{uuid.uuid4().hex[:12].upper()}"

        new_expense = Expense(
            id=expense_id,
            report_id=report_id,
            expense_type=expense_input.expense_type.value,
            vendor=expense_input.vendor,
            amount=expense_input.amount,
            currency=expense_input.currency,
            transaction_date=expense_input.transaction_date,
            city=expense_input.city,
            payment_type=expense_input.payment_type.value,
            notes=expense_input.notes,
            status=expense_status,
            card_transaction_id=matched_card_id,
        )
        expense_repo.create(new_expense, db)

        # Link receipt if provided
        receipt_id_for_expense: Optional[str] = None
        if expense_input.receipt_id:
            existing_rcp = receipt_repo.get_by_id(expense_input.receipt_id, db)
            if existing_rcp:
                expense_repo.link_receipt(expense_id, expense_input.receipt_id, db)
                receipt_id_for_expense = expense_input.receipt_id
        else:
            # Auto-register a receipt row from the hash computed in Step 6
            new_receipt = Receipt(
                id=f"RCP-{uuid.uuid4().hex[:12].upper()}",
                employee_id=employee_id,
                receipt_hash=receipt_hash,
                ocr_confidence=expense_input.ocr_confidence,
            )
            receipt_repo.create(new_receipt, db)
            expense_repo.link_receipt(expense_id, new_receipt.id, db)
            receipt_id_for_expense = new_receipt.id

        # Persist hotel itemization lines
        if expense_input.expense_type.value == "HOTEL" and expense_input.itemization:
            total_itemization = 0.0
            for line_input in expense_input.itemization:
                line_total = line_input.room_rate + line_input.taxes + line_input.incidentals
                total_itemization += line_total
                line = HotelItemizationLine(
                    id=f"HIL-{uuid.uuid4().hex[:12].upper()}",
                    expense_id=expense_id,
                    night_date=line_input.night_date,
                    room_rate=line_input.room_rate,
                    taxes=line_input.taxes,
                    incidentals=line_input.incidentals,
                    line_total=line_total,
                )
                db.add(line)

            # Check itemization sum mismatch
            tolerance = settings.itemization_sum_tolerance
            if abs(total_itemization - expense_input.amount) > tolerance:
                exp_warnings.append(ValidationWarning(
                    code=WarningCode.ITEMIZATION_SUM_MISMATCH,
                    message=(
                        f"Itemization lines sum to "
                        f"{expense_input.currency} {total_itemization:,.2f} "
                        f"but the expense total is "
                        f"{expense_input.currency} {expense_input.amount:,.2f}. "
                        f"Difference: {abs(total_itemization - expense_input.amount):,.2f}."
                    ),
                    severity=WarningSeverity.WARNING,
                    field="itemization",
                ))

        # Persist type-specific detail rows
        if expense_input.expense_type.value == "FLIGHT" and expense_input.airfare_detail:
            ad = expense_input.airfare_detail
            db.add(AirfareDetail(
                id=f"AFD-{uuid.uuid4().hex[:12].upper()}",
                expense_id=expense_id,
                origin=ad.origin,
                destination=ad.destination,
                flight_number=ad.flight_number,
                travel_class=ad.travel_class.value,
                ticket_number=ad.ticket_number,
            ))

        if expense_input.expense_type.value == "TAXI" and expense_input.taxi_detail:
            td = expense_input.taxi_detail
            db.add(TaxiDetail(
                id=f"TXD-{uuid.uuid4().hex[:12].upper()}",
                expense_id=expense_id,
                from_location=td.from_location,
                to_location=td.to_location,
                distance_km=td.distance_km,
            ))

        if expense_input.expense_type.value == "MEAL" and expense_input.meal_detail:
            md = expense_input.meal_detail
            db.add(MealDetail(
                id=f"MLD-{uuid.uuid4().hex[:12].upper()}",
                expense_id=expense_id,
                meal_type=md.meal_type.value,
                attendees=md.attendees,
            ))

        total_warning_count += len(exp_warnings)
        processed.append(ProcessedExpense(
            expense_id=expense_id,
            vendor=expense_input.vendor,
            expense_type=expense_input.expense_type,
            amount=expense_input.amount,
            currency=expense_input.currency,
            status=ExpenseStatus(expense_status),
            card_transaction_id=matched_card_id,
            receipt_id=receipt_id_for_expense,
            warnings=exp_warnings,
        ))

    # ================================================================
    # STEP 9 (continued) — Update report totals and determine status
    # ================================================================
    new_total = expense_report_repo.update_total(report_id, db)

    # Include expense-level warnings in the MANUAL_REVIEW determination
    has_any_warnings = bool(report_level_warnings) or any(p.warnings for p in processed)
    final_status_value = "MANUAL_REVIEW" if has_any_warnings else "DRAFT"
    expense_report_repo.update_status(report_id, final_status_value, db)

    # Commit everything in one transaction
    db.commit()

    # ================================================================
    # STEP 9 (continued) — Audit: Expenses Added
    # ================================================================
    audit_service.log_event(
        event_type=AuditEvent.EXPENSES_ADDED,
        entity_type=AuditEntity.EXPENSE_REPORT,
        entity_id=report_id,
        employee_id=employee_id,
        description=(
            f"{len(processed)} expense(s) added to report {report_id!r}. "
            f"Final status: {final_status_value}."
        ),
        db=db,
        metadata_dict={
            "expenseCount": len(processed),
            "warningCount": total_warning_count,
            "finalStatus": final_status_value,
            "totalAmount": new_total,
        },
    )
    db.commit()  # Commit the audit entry

    # ================================================================
    # Policy validation audit entry
    # ================================================================
    audit_service.log_event(
        event_type=AuditEvent.POLICY_VALIDATION_COMPLETED,
        entity_type=AuditEntity.EXPENSE_REPORT,
        entity_id=report_id,
        employee_id=employee_id,
        description=f"Policy validation completed. {total_warning_count} warning(s) generated.",
        db=db,
        metadata_dict={"warningCount": total_warning_count, "policyName": policy_name},
    )
    db.commit()

    # ================================================================
    # Build and return the response envelope
    # ================================================================
    matched_count       = sum(1 for p in processed if p.status == ExpenseStatus.MATCHED)
    pending_count       = sum(1 for p in processed if p.status == ExpenseStatus.PENDING)
    manual_review_count = sum(1 for p in processed if p.status == ExpenseStatus.MANUAL_REVIEW)

    return ExpensesSubmitResponse(
        report_id=report_id,
        status=ReportStatus(final_status_value),
        warnings=report_level_warnings,
        processed_expenses=processed,
        summary=SubmitSummary(
            total_expenses=len(processed),
            total_amount=new_total,
            currency=expenses[0].currency if expenses else "INR",
            matched_count=matched_count,
            pending_count=pending_count,
            manual_review_count=manual_review_count,
            warning_count=total_warning_count,
        ),
    )
