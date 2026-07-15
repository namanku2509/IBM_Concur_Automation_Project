"""
tests/test_trip_matching.py
-----------------------------
Unit tests for services/trip_matching_service.py and
repositories/trip_repo.py matching functions.

Uses an in-memory SQLite database via the conftest fixtures so no
actual SQLite file is created on disk during test runs.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from models.employee import Employee
from models.travel_policy import TravelPolicy
from models.trip import Trip
from services.trip_matching_service import find_matching_trip


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture()
def db_session(tmp_path):
    """
    Provide a real SQLite in-memory session with all tables created.
    Each test gets a clean database.
    """
    import os
    os.environ["DB_PATH"] = ":memory:"

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base

    # Import all models so metadata is populated
    import models.employee
    import models.travel_policy
    import models.trip
    import models.expense_report
    import models.expense
    import models.hotel_itemization
    import models.airfare_detail
    import models.taxi_detail
    import models.meal_detail
    import models.corporate_card_transaction
    import models.receipt
    import models.audit_log

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed a policy and employee so FK constraints pass
    policy = TravelPolicy(name="STANDARD", description="Standard policy")
    session.add(policy)
    session.flush()

    emp = Employee(
        id="EMP001",
        name="Test User",
        email="test@test.com",
        travel_policy_name="STANDARD",
        department="Engineering",
        is_active=True,
    )
    session.add(emp)
    session.flush()

    yield session
    session.close()


def _add_trip(
    db,
    trip_id: str,
    city: str,
    start: date,
    end: date,
    status: str = "ACTIVE",
) -> Trip:
    trip = Trip(
        id=trip_id,
        employee_id="EMP001",
        destination_city=city,
        start_date=start,
        end_date=end,
        purpose="Test trip",
        status=status,
    )
    db.add(trip)
    db.flush()
    return trip


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #

class TestFindMatchingTrip:
    def test_matches_exact_city_and_date(self, db_session):
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 7, 21)],
            expense_cities=["Bengaluru"],
            db=db_session,
        )
        assert result is not None
        assert result.id == "T1"

    def test_matches_with_city_case_insensitive(self, db_session):
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 7, 21)],
            expense_cities=["bengaluru"],  # lowercase
            db=db_session,
        )
        assert result is not None

    def test_matches_within_tolerance_window(self, db_session):
        """Expense date is 1 day before trip start — should match within tolerance."""
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 7, 19)],  # 1 day before trip start
            expense_cities=["Bengaluru"],
            db=db_session,
        )
        assert result is not None

    def test_no_match_when_city_differs(self, db_session):
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 7, 21)],
            expense_cities=["Mumbai"],  # wrong city
            db=db_session,
        )
        assert result is None

    def test_no_match_when_date_far_outside_window(self, db_session):
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 8, 10)],  # 18 days after trip ends
            expense_cities=["Bengaluru"],
            db=db_session,
        )
        assert result is None

    def test_no_match_when_no_trips_exist(self, db_session):
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 7, 21)],
            expense_cities=["Bengaluru"],
            db=db_session,
        )
        assert result is None

    def test_no_match_for_completed_trip(self, db_session):
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23), status="COMPLETED")
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 7, 21)],
            expense_cities=["Bengaluru"],
            db=db_session,
        )
        assert result is None

    def test_selects_correct_trip_from_multiple(self, db_session):
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        _add_trip(db_session, "T2", "Mumbai",    date(2026, 8, 10), date(2026, 8, 12))
        result = find_matching_trip(
            employee_id="EMP001",
            expense_dates=[date(2026, 8, 11)],
            expense_cities=["Mumbai"],
            db=db_session,
        )
        assert result is not None
        assert result.id == "T2"

    def test_matches_any_expense_date_against_trip(self, db_session):
        """If any expense date matches the trip window, the trip is selected."""
        _add_trip(db_session, "T1", "Bengaluru", date(2026, 7, 20), date(2026, 7, 23))
        result = find_matching_trip(
            employee_id="EMP001",
            # First date doesn't match, second does
            expense_dates=[date(2026, 8, 1), date(2026, 7, 22)],
            expense_cities=["Bengaluru"],
            db=db_session,
        )
        assert result is not None
        assert result.id == "T1"
