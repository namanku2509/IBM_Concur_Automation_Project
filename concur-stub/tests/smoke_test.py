"""
tests/smoke_test.py
--------------------
End-to-end smoke tests for all four demo scenarios.

These tests run against a LIVE server (not TestClient) and require:
  1. The server to be running: uvicorn main:app --reload --port 8000
  2. The seed data to be present (automatically inserted on first startup)

Run with:
    cd concur-stub
    pytest tests/smoke_test.py -v

Each test represents one of the four documented demo scenarios:
  1. Happy path       — EMP001 Bengaluru trip, cards match, DRAFT status
  2. Policy violation — EMP002 hotel 7500 > 6000 limit → warning, DRAFT
  3. Unmatched trip   — no trip in DB for submitted city/date → MANUAL_REVIEW
  4. Duplicate detect — same expense submitted twice → DUPLICATE warning
"""

from __future__ import annotations

from datetime import date

import pytest
import httpx

BASE_URL = "http://localhost:8000/api/v4"
HEADERS  = {"X-Api-Key": "concur-stub-dev-key", "Content-Type": "application/json"}


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _create_report(client: httpx.Client, report_id: str, employee_id: str = "EMP001") -> dict:
    payload = {
        "reportId":        report_id,
        "employeeId":      employee_id,
        "reportName":      f"Smoke Test Report {report_id}",
        "businessPurpose": "Smoke test",
        "travelPolicy":    "STANDARD",
        "expenseCategory": "TRAVEL",
        "currency":        "INR",
    }
    r = client.post(f"{BASE_URL}/expense-reports", json=payload, headers=HEADERS)
    assert r.status_code == 201, f"Create report failed: {r.text}"
    return r.json()


def _submit_expenses(
    client: httpx.Client,
    report_id: str,
    expenses: list[dict],
    employee_id: str = "EMP001",
) -> dict:
    payload = {"employeeId": employee_id, "expenses": expenses}
    r = client.post(
        f"{BASE_URL}/expense-reports/{report_id}/expenses",
        json=payload,
        headers=HEADERS,
    )
    return r


# ------------------------------------------------------------------ #
# Scenario 1: Happy path                                               #
# ------------------------------------------------------------------ #

@pytest.mark.smoke
def test_scenario_1_happy_path():
    """
    EMP001 submits a taxi expense matching CCT003 (Ola, 650 INR).
    Trip TRIP001 (Bengaluru, Jul 20–23) should match.
    Expected: DRAFT report, MATCHED expense, zero warnings.
    """
    with httpx.Client(timeout=10) as client:
        _create_report(client, "SMOKE-RPT-001")

        expense = {
            "expenseType":     "TAXI",
            "vendor":          "Ola",
            "amount":          650.0,
            "currency":        "INR",
            "transactionDate": "2026-07-20",
            "city":            "Bengaluru",
            "paymentType":     "CORPORATE_CARD",
        }
        r = _submit_expenses(client, "SMOKE-RPT-001", [expense])
        assert r.status_code == 200, r.text

        body = r.json()
        assert body["status"] == "DRAFT", f"Expected DRAFT, got: {body['status']}"
        assert body["warnings"] == [], f"Expected no report warnings: {body['warnings']}"

        exp = body["processedExpenses"][0]
        assert exp["status"] == "MATCHED", f"Expected MATCHED, got: {exp['status']}"
        assert exp["warnings"] == [], f"Unexpected expense warnings: {exp['warnings']}"

        # Verify audit log captured events
        audit_r = client.get(f"http://localhost:8000/admin/audit-log", headers=HEADERS)
        # Just check the page loads
        assert audit_r.status_code == 200


# ------------------------------------------------------------------ #
# Scenario 2: Policy violation — hotel over STANDARD limit            #
# ------------------------------------------------------------------ #

@pytest.mark.smoke
def test_scenario_2_hotel_policy_violation():
    """
    EMP002 submits a hotel with room rate 7500 INR (STANDARD limit = 6000).
    Expected: DRAFT report (no trip-level warnings), HOTEL_NIGHTLY_LIMIT_EXCEEDED
    expense-level warning.
    """
    with httpx.Client(timeout=10) as client:
        _create_report(client, "SMOKE-RPT-002", employee_id="EMP002")

        expense = {
            "expenseType":     "HOTEL",
            "vendor":          "Taj Hotels",
            "amount":          15000.0,
            "currency":        "INR",
            "transactionDate": "2026-07-15",
            "city":            "Hyderabad",
            "paymentType":     "CORPORATE_CARD",
            "itemization": [
                {"nightDate": "2026-07-15", "roomRate": 7500.0, "taxes": 1350.0, "incidentals": 150.0},
                {"nightDate": "2026-07-16", "roomRate": 7500.0, "taxes": 1350.0, "incidentals": 150.0},
            ],
        }
        r = _submit_expenses(client, "SMOKE-RPT-002", [expense], employee_id="EMP002")
        assert r.status_code == 200, r.text

        body = r.json()
        exp  = body["processedExpenses"][0]
        warning_codes = [w["code"] for w in exp["warnings"]]
        assert "HOTEL_NIGHTLY_LIMIT_EXCEEDED" in warning_codes, (
            f"Expected HOTEL_NIGHTLY_LIMIT_EXCEEDED in {warning_codes}"
        )


# ------------------------------------------------------------------ #
# Scenario 3: Unmatched trip → MANUAL_REVIEW                          #
# ------------------------------------------------------------------ #

@pytest.mark.smoke
def test_scenario_3_unmatched_trip():
    """
    Submit expenses for a city/date combination with no seeded trip.
    Expected: MANUAL_REVIEW report status, TRIP_NOT_MATCHED report-level warning.
    """
    with httpx.Client(timeout=10) as client:
        _create_report(client, "SMOKE-RPT-003")

        expense = {
            "expenseType":     "TAXI",
            "vendor":          "Rapido",
            "amount":          380.0,
            "currency":        "INR",
            "transactionDate": "2026-09-01",   # No trip seeded for this date
            "city":            "Pune",          # No trip seeded for this city
            "paymentType":     "PERSONAL_CASH",
        }
        r = _submit_expenses(client, "SMOKE-RPT-003", [expense])
        assert r.status_code == 200, r.text

        body = r.json()
        assert body["status"] == "MANUAL_REVIEW", (
            f"Expected MANUAL_REVIEW, got: {body['status']}"
        )
        report_warning_codes = [w["code"] for w in body["warnings"]]
        assert "TRIP_NOT_MATCHED" in report_warning_codes, (
            f"Expected TRIP_NOT_MATCHED in {report_warning_codes}"
        )


# ------------------------------------------------------------------ #
# Scenario 4: Duplicate detection                                     #
# ------------------------------------------------------------------ #

@pytest.mark.smoke
def test_scenario_4_duplicate_detection():
    """
    Submit the same expense for EMP001 twice (different report IDs).
    Second submission should include DUPLICATE_RECEIPT_DETECTED warning.
    """
    with httpx.Client(timeout=10) as client:
        expense = {
            "expenseType":     "MEAL",
            "vendor":          "Test Bistro Unique",
            "amount":          850.0,
            "currency":        "INR",
            "transactionDate": "2026-07-21",
            "city":            "Bengaluru",
            "paymentType":     "PERSONAL_CASH",
        }

        # First submission
        _create_report(client, "SMOKE-RPT-004A")
        r1 = _submit_expenses(client, "SMOKE-RPT-004A", [expense])
        assert r1.status_code == 200, r1.text

        # Second submission — same expense
        _create_report(client, "SMOKE-RPT-004B")
        r2 = _submit_expenses(client, "SMOKE-RPT-004B", [expense])
        assert r2.status_code == 200, r2.text

        body = r2.json()
        exp  = body["processedExpenses"][0]
        warning_codes = [w["code"] for w in exp["warnings"]]
        assert "DUPLICATE_RECEIPT_DETECTED" in warning_codes, (
            f"Expected DUPLICATE_RECEIPT_DETECTED in {warning_codes}"
        )


# ------------------------------------------------------------------ #
# Scenario 5: Pre-flight — missing itemization for HOTEL              #
# ------------------------------------------------------------------ #

@pytest.mark.smoke
def test_scenario_5_preflight_missing_itemization():
    """
    Submit a HOTEL expense without itemization.
    Expected: HTTP 422, ITEMIZATION_REQUIRED in errors.
    """
    with httpx.Client(timeout=10) as client:
        _create_report(client, "SMOKE-RPT-005")

        expense = {
            "expenseType":     "HOTEL",
            "vendor":          "Some Hotel",
            "amount":          12000.0,
            "currency":        "INR",
            "transactionDate": "2026-07-20",
            "city":            "Bengaluru",
            "paymentType":     "CORPORATE_CARD",
            # itemization intentionally omitted
        }
        r = _submit_expenses(client, "SMOKE-RPT-005", [expense])
        assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"

        detail = r.json()["detail"]
        assert detail["status"] == "PREFLIGHT_FAILED"
        error_codes = [e["code"] for e in detail["errors"]]
        assert "ITEMIZATION_REQUIRED" in error_codes


# ------------------------------------------------------------------ #
# Admin dashboard smoke                                                #
# ------------------------------------------------------------------ #

@pytest.mark.smoke
def test_admin_dashboard_loads():
    """Verify all admin dashboard pages return HTTP 200."""
    with httpx.Client(timeout=10) as client:
        for path in ["/admin/", "/admin/reports", "/admin/employees",
                     "/admin/card-transactions", "/admin/audit-log"]:
            r = client.get(f"http://localhost:8000{path}")
            assert r.status_code == 200, f"Admin page {path} returned {r.status_code}"
