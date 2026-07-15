"""
tests/conftest.py
-----------------
Shared pytest fixtures for the entire test suite.

Provides:
  - db_session: a fresh in-memory SQLite session per test, with all
    tables created and seed data loaded.
  - client: a FastAPI TestClient wired to the same in-memory DB.

The in-memory database is isolated per test — no test affects another.
"""

from __future__ import annotations

import os
import pytest
from datetime import date
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Provide a clean in-memory SQLite session for each test function.
    All tables are created; a minimal seed dataset is inserted.
    """
    # Point config at in-memory DB before importing anything that reads settings
    os.environ.setdefault("DB_PATH", ":memory:")

    from database import Base
    import models.employee           # noqa: F401
    import models.travel_policy      # noqa: F401
    import models.trip               # noqa: F401
    import models.expense_report     # noqa: F401
    import models.expense            # noqa: F401
    import models.hotel_itemization  # noqa: F401
    import models.airfare_detail     # noqa: F401
    import models.taxi_detail        # noqa: F401
    import models.meal_detail        # noqa: F401
    import models.corporate_card_transaction  # noqa: F401
    import models.receipt            # noqa: F401
    import models.audit_log          # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = TestSession()

    _insert_test_seed(db)
    db.commit()

    yield db
    db.close()


def _insert_test_seed(db: Session) -> None:
    """Insert minimal reference data needed by most tests."""
    import json
    from models.travel_policy import TravelPolicy, PolicyRule
    from models.employee import Employee
    from models.trip import Trip
    from models.corporate_card_transaction import CorporateCardTransaction

    # Travel policies
    db.add(TravelPolicy(name="STANDARD",  description="Standard policy"))
    db.add(TravelPolicy(name="EXECUTIVE", description="Executive policy"))
    db.flush()

    # Policy rules — STANDARD
    rules_std = [
        ("HOTEL",  "NIGHTLY_LIMIT",         "6000",          "INR"),
        ("MEAL",   "MEAL_LIMIT",             "1000",          "INR"),
        ("FLIGHT", "MAX_TRAVEL_CLASS",       '"ECONOMY"',     None),
        ("ALL",    "ALLOWED_CURRENCIES",     '["INR"]',       None),
        ("ALL",    "ALLOWED_PAYMENT_TYPES",  '["CORPORATE_CARD","PERSONAL_CASH","CORPORATE_CASH"]', None),
        ("ALL",    "OCR_CONFIDENCE_THRESHOLD", "0.75",        None),
    ]
    for exp_type, key, value, currency in rules_std:
        db.add(PolicyRule(policy_name="STANDARD", expense_type=exp_type,
                          rule_key=key, rule_value=value, currency=currency))

    # Policy rules — EXECUTIVE
    rules_exec = [
        ("HOTEL",  "NIGHTLY_LIMIT",         "12000",         "INR"),
        ("MEAL",   "MEAL_LIMIT",             "2500",          "INR"),
        ("FLIGHT", "MAX_TRAVEL_CLASS",       '"BUSINESS"',    None),
        ("ALL",    "ALLOWED_CURRENCIES",     '["INR","USD","GBP"]', None),
        ("ALL",    "ALLOWED_PAYMENT_TYPES",  '["CORPORATE_CARD","PERSONAL_CASH","CORPORATE_CASH"]', None),
        ("ALL",    "OCR_CONFIDENCE_THRESHOLD", "0.70",        None),
    ]
    for exp_type, key, value, currency in rules_exec:
        db.add(PolicyRule(policy_name="EXECUTIVE", expense_type=exp_type,
                          rule_key=key, rule_value=value, currency=currency))
    db.flush()

    # Employees
    db.add(Employee(id="EMP001", name="Priya Sharma",  email="priya@test.com",
                    travel_policy_name="STANDARD",  department="Consulting", is_active=True))
    db.add(Employee(id="EMP002", name="Arjun Mehta",   email="arjun@test.com",
                    travel_policy_name="STANDARD",  department="Engineering", is_active=True))
    db.add(Employee(id="EMP003", name="Kavita Nair",   email="kavita@test.com",
                    travel_policy_name="EXECUTIVE", department="Consulting", is_active=True))
    db.add(Employee(id="EMP_INACTIVE", name="Inactive User", email="inactive@test.com",
                    travel_policy_name="STANDARD",  department="HR", is_active=False))
    db.flush()

    # Trip for EMP001 — Bengaluru (happy-path scenario)
    db.add(Trip(id="TRIP001", employee_id="EMP001", destination_city="Bengaluru",
                start_date=date(2026, 7, 20), end_date=date(2026, 7, 23),
                purpose="Test trip", status="ACTIVE"))

    # Card transactions for EMP001 — designed to match test expenses
    db.add(CorporateCardTransaction(
        id="CCT001", employee_id="EMP001", vendor="Marriott",
        amount=18000.0, currency="INR",
        transaction_date=date(2026, 7, 20), card_last_four="4242", status="AVAILABLE",
    ))
    db.add(CorporateCardTransaction(
        id="CCT002", employee_id="EMP001", vendor="IndiGo Airlines",
        amount=5500.0, currency="INR",
        transaction_date=date(2026, 7, 19), card_last_four="4242", status="AVAILABLE",
    ))
    db.add(CorporateCardTransaction(
        id="CCT003", employee_id="EMP001", vendor="Ola",
        amount=650.0, currency="INR",
        transaction_date=date(2026, 7, 20), card_last_four="4242", status="AVAILABLE",
    ))
    db.flush()
