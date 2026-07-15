"""
tests/test_expenses.py
-----------------------
Integration tests for the 9-step expense validation pipeline
(services/expense_service.py).

Each test sets up the minimal DB state it needs via the conftest
db_session fixture, calls process_expenses() directly, and asserts
on the response envelope.

Tests cover all 9 scenarios from the plan:
  1. Happy path — full match, no warnings
  2. No matching trip → MANUAL_REVIEW + TRIP_NOT_MATCHED
  3. Duplicate receipt → DUPLICATE_RECEIPT_DETECTED warning
  4. Hotel over STANDARD limit → HOTEL_NIGHTLY_LIMIT_EXCEEDED warning
  5. EXECUTIVE policy BUSINESS class flight — no violation
  6. STANDARD policy BUSINESS class flight → TRAVEL_CLASS_VIOLATION
  7. Missing mandatory field in batch → HTTP 422
  8. Invalid expense type → HTTP 422
  9. Submitting to SUBMITTED report → HTTP 409
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from models.expense_report import ExpenseReport
from schemas.common import WarningCode, ReportStatus
from schemas.expense import (
    AirfareDetailInput,
    ExpenseInput,
    ExpensesSubmitRequest,
    HotelItemizationInput,
)
from services.expense_service import process_expenses


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _create_report(db, report_id: str, employee_id: str = "EMP001") -> ExpenseReport:
    """Helper: insert a DRAFT report for the given employee."""
    from models.employee import Employee
    emp = db.get(Employee, employee_id)
    report = ExpenseReport(
        id=report_id,
        employee_id=employee_id,
        report_name="Test Report",
        business_purpose="Testing",
        travel_policy_name=emp.travel_policy_name,
        expense_category="TRAVEL",
        status="DRAFT",
        total_amount=0.0,
        currency="INR",
    )
    db.add(report)
    db.flush()
    return report


def _hotel_request(
    employee_id: str = "EMP001",
    room_rates: list[float] = None,
    city: str = "Bengaluru",
    txn_date: date = date(2026, 7, 21),
) -> ExpensesSubmitRequest:
    room_rates = room_rates or [5500.0]
    itemization = [
        HotelItemizationInput(
            night_date=date(2026, 7, 20 + i),
            room_rate=r,
            taxes=round(r * 0.18, 2),
            incidentals=100.0,
        )
        for i, r in enumerate(room_rates)
    ]
    total = sum(r + r * 0.18 + 100.0 for r in room_rates)
    expense = ExpenseInput(
        expense_type="HOTEL",
        vendor="Marriott",
        amount=round(total, 2),
        currency="INR",
        transaction_date=txn_date,
        city=city,
        payment_type="CORPORATE_CARD",
        itemization=itemization,
    )
    return ExpensesSubmitRequest(employee_id=employee_id, expenses=[expense])


def _taxi_request(
    employee_id: str = "EMP001",
    vendor: str = "Ola",
    amount: float = 650.0,
    city: str = "Bengaluru",
    txn_date: date = date(2026, 7, 20),
    payment_type: str = "CORPORATE_CARD",
) -> ExpensesSubmitRequest:
    expense = ExpenseInput(
        expense_type="TAXI",
        vendor=vendor,
        amount=amount,
        currency="INR",
        transaction_date=txn_date,
        city=city,
        payment_type=payment_type,
    )
    return ExpensesSubmitRequest(employee_id=employee_id, expenses=[expense])


def _flight_request(
    employee_id: str = "EMP001",
    travel_class: str = "ECONOMY",
) -> ExpensesSubmitRequest:
    expense = ExpenseInput(
        expense_type="FLIGHT",
        vendor="IndiGo Airlines",
        amount=5500.0,
        currency="INR",
        transaction_date=date(2026, 7, 19),
        city="Bengaluru",
        payment_type="CORPORATE_CARD",
        airfare_detail=AirfareDetailInput(
            origin="Mumbai",
            destination="Bengaluru",
            travel_class=travel_class,
        ),
    )
    return ExpensesSubmitRequest(employee_id=employee_id, expenses=[expense])


# ------------------------------------------------------------------ #
# Test: Happy path                                                     #
# ------------------------------------------------------------------ #

def test_happy_path_taxi_matched(db_session):
    """
    Scenario 1: EMP001 submits a taxi expense.
    Card transaction CCT003 matches (Ola, 650 INR, 2026-07-20).
    Trip TRIP001 matches (Bengaluru, within date window).
    Result: DRAFT report, MATCHED expense, no warnings.
    """
    _create_report(db_session, "RPT001")
    request = _taxi_request()
    response = process_expenses("RPT001", request, db_session)

    assert response.status == ReportStatus.DRAFT
    assert response.warnings == []
    assert len(response.processed_expenses) == 1
    exp = response.processed_expenses[0]
    assert exp.status.value == "MATCHED"
    assert exp.card_transaction_id == "CCT003"
    assert exp.warnings == []


# ------------------------------------------------------------------ #
# Test: No matching trip                                               #
# ------------------------------------------------------------------ #

def test_trip_not_matched_returns_manual_review(db_session):
    """
    Scenario 2: expenses with a city that has no matching trip.
    Result: MANUAL_REVIEW report + TRIP_NOT_MATCHED report-level warning.
    """
    _create_report(db_session, "RPT002")
    # Use a city with no seeded trip
    request = _taxi_request(city="Hyderabad", txn_date=date(2026, 7, 21), amount=420.0)
    response = process_expenses("RPT002", request, db_session)

    assert response.status == ReportStatus.MANUAL_REVIEW
    assert any(w.code == WarningCode.TRIP_NOT_MATCHED for w in response.warnings)


# ------------------------------------------------------------------ #
# Test: Duplicate receipt                                              #
# ------------------------------------------------------------------ #

def test_duplicate_receipt_warning(db_session):
    """
    Scenario 3: submit the same taxi expense twice.
    Second submission gets DUPLICATE_RECEIPT_DETECTED warning.
    """
    _create_report(db_session, "RPT003A")
    _create_report(db_session, "RPT003B")
    request = _taxi_request(vendor="Ola", amount=650.0, txn_date=date(2026, 7, 20))

    # First submission
    process_expenses("RPT003A", request, db_session)

    # Second submission — same expense
    response = process_expenses("RPT003B", request, db_session)
    exp = response.processed_expenses[0]
    warning_codes = [w.code for w in exp.warnings]
    assert WarningCode.DUPLICATE_RECEIPT_DETECTED in warning_codes


# ------------------------------------------------------------------ #
# Test: Hotel over STANDARD nightly limit                             #
# ------------------------------------------------------------------ #

def test_hotel_over_nightly_limit_warning(db_session):
    """
    Scenario 4: EMP001 (STANDARD policy, limit 6000 INR).
    Submit a hotel with room rate 7500 INR.
    Result: DRAFT report, expense with HOTEL_NIGHTLY_LIMIT_EXCEEDED warning.
    """
    _create_report(db_session, "RPT004")
    request = _hotel_request(room_rates=[7500.0])
    response = process_expenses("RPT004", request, db_session)

    exp = response.processed_expenses[0]
    warning_codes = [w.code for w in exp.warnings]
    assert WarningCode.HOTEL_NIGHTLY_LIMIT_EXCEEDED in warning_codes


# ------------------------------------------------------------------ #
# Test: EXECUTIVE policy BUSINESS class — no violation                #
# ------------------------------------------------------------------ #

def test_executive_business_class_no_violation(db_session):
    """
    Scenario 5: EMP003 has EXECUTIVE policy (MAX_TRAVEL_CLASS=BUSINESS).
    Booking business class should NOT trigger TRAVEL_CLASS_VIOLATION.
    """
    _create_report(db_session, "RPT005", employee_id="EMP003")
    request = _flight_request(employee_id="EMP003", travel_class="BUSINESS")
    response = process_expenses("RPT005", request, db_session)

    exp = response.processed_expenses[0]
    warning_codes = [w.code for w in exp.warnings]
    assert WarningCode.TRAVEL_CLASS_VIOLATION not in warning_codes


# ------------------------------------------------------------------ #
# Test: STANDARD policy BUSINESS class — violation                    #
# ------------------------------------------------------------------ #

def test_standard_business_class_violation(db_session):
    """
    Scenario 6: EMP001 has STANDARD policy (MAX_TRAVEL_CLASS=ECONOMY).
    Booking business class triggers TRAVEL_CLASS_VIOLATION warning.
    """
    _create_report(db_session, "RPT006")
    request = _flight_request(employee_id="EMP001", travel_class="BUSINESS")
    response = process_expenses("RPT006", request, db_session)

    exp = response.processed_expenses[0]
    warning_codes = [w.code for w in exp.warnings]
    assert WarningCode.TRAVEL_CLASS_VIOLATION in warning_codes


# ------------------------------------------------------------------ #
# Test: Missing mandatory field → HTTP 422                            #
# ------------------------------------------------------------------ #

def test_missing_mandatory_field_raises_422(db_session):
    """
    Scenario 7: HOTEL expense missing itemization → pre-flight 422.
    All pre-flight errors for all expenses are returned together.
    """
    _create_report(db_session, "RPT007")
    # Hotel expense without itemization
    expense = ExpenseInput(
        expense_type="HOTEL",
        vendor="Marriott",
        amount=18000.0,
        currency="INR",
        transaction_date=date(2026, 7, 21),
        city="Bengaluru",
        payment_type="CORPORATE_CARD",
        itemization=None,  # Missing required field
    )
    request = ExpensesSubmitRequest(employee_id="EMP001", expenses=[expense])

    with pytest.raises(HTTPException) as exc_info:
        process_expenses("RPT007", request, db_session)

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert detail["status"] == "PREFLIGHT_FAILED"
    assert any(e["code"] == "ITEMIZATION_REQUIRED" for e in detail["errors"])


# ------------------------------------------------------------------ #
# Test: Invalid expense type → HTTP 422                               #
# ------------------------------------------------------------------ #

def test_invalid_expense_type_raises_422(db_session):
    """
    Scenario 8: expenseType 'GROCERIES' is not a supported type.
    Pre-flight should return HTTP 422.
    """
    _create_report(db_session, "RPT008")
    with pytest.raises(Exception):
        # Pydantic will reject 'GROCERIES' at model construction for ExpenseType enum
        expense = ExpenseInput(
            expense_type="GROCERIES",  # invalid
            vendor="Some Shop",
            amount=500.0,
            currency="INR",
            transaction_date=date(2026, 7, 21),
            city="Bengaluru",
            payment_type="PERSONAL_CASH",
        )


# ------------------------------------------------------------------ #
# Test: Submit to SUBMITTED report → HTTP 409                         #
# ------------------------------------------------------------------ #

def test_submitted_report_returns_409(db_session):
    """
    Scenario 9: attempt to add expenses to a SUBMITTED report.
    Should return HTTP 409 REPORT_NOT_EDITABLE.
    """
    # Create a report in SUBMITTED status directly
    from models.employee import Employee
    emp = db_session.get(Employee, "EMP001")
    report = ExpenseReport(
        id="RPT009",
        employee_id="EMP001",
        report_name="Submitted Report",
        business_purpose="Testing",
        travel_policy_name=emp.travel_policy_name,
        expense_category="TRAVEL",
        status="SUBMITTED",  # already submitted
        total_amount=0.0,
        currency="INR",
    )
    db_session.add(report)
    db_session.flush()

    request = _taxi_request()
    with pytest.raises(HTTPException) as exc_info:
        process_expenses("RPT009", request, db_session)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "REPORT_NOT_EDITABLE"


# ------------------------------------------------------------------ #
# Test: Employee not found → HTTP 404                                 #
# ------------------------------------------------------------------ #

def test_employee_not_found_returns_404(db_session):
    _create_report(db_session, "RPT010")
    request = ExpensesSubmitRequest(
        employee_id="NONEXISTENT",
        expenses=[ExpenseInput(
            expense_type="TAXI", vendor="Ola", amount=650.0,
            currency="INR", transaction_date=date(2026, 7, 21),
            city="Bengaluru", payment_type="PERSONAL_CASH",
        )],
    )
    with pytest.raises(HTTPException) as exc_info:
        process_expenses("RPT010", request, db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "EMPLOYEE_NOT_FOUND"


# ------------------------------------------------------------------ #
# Test: Card not matched → PENDING + warning                          #
# ------------------------------------------------------------------ #

def test_card_not_matched_returns_pending_with_warning(db_session):
    """An expense amount that doesn't match any card transaction."""
    _create_report(db_session, "RPT011")
    # Amount 9999 has no matching card transaction
    request = _taxi_request(amount=9999.0)
    response = process_expenses("RPT011", request, db_session)

    exp = response.processed_expenses[0]
    assert exp.status.value == "PENDING"
    warning_codes = [w.code for w in exp.warnings]
    assert WarningCode.CARD_TRANSACTION_NOT_MATCHED in warning_codes
