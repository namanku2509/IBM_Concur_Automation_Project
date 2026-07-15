"""
repositories/trip_repo.py
--------------------------
Database access layer for the Trip domain.

Includes the trip matching query used by trip_matching_service.py.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from models.trip import Trip


def get_by_id(trip_id: str, db: Session) -> Trip | None:
    return db.get(Trip, trip_id)


def create(trip: Trip, db: Session) -> Trip:
    db.add(trip)
    db.flush()  # Get the DB-generated defaults without committing
    return trip


def get_active_trips_for_employee(employee_id: str, db: Session) -> list[Trip]:
    """Return all non-completed trips for an employee."""
    return (
        db.query(Trip)
        .filter(
            Trip.employee_id == employee_id,
            Trip.status != "COMPLETED",
        )
        .order_by(Trip.start_date)
        .all()
    )


def find_matching_trip(
    employee_id: str,
    expense_dates: list[date],
    expense_cities: list[str],
    db: Session,
    date_tolerance_days: int = 1,
) -> Trip | None:
    """
    Find the best matching trip for a set of expense dates and cities.

    Matching criteria (all three must hold for a trip to qualify):
      1. Trip belongs to this employee
      2. At least one expense date falls within the trip's date window
         (extended by ±date_tolerance_days on each end)
      3. The trip's destination_city matches at least one expense city
         (case-insensitive)

    Returns the first qualifying trip, or None.
    """
    active_trips = get_active_trips_for_employee(employee_id, db)
    normalised_cities = {c.lower().strip() for c in expense_cities}

    for trip in active_trips:
        # City match — case-insensitive
        if trip.destination_city.lower().strip() not in normalised_cities:
            continue

        # Date window match with tolerance buffer
        window_start = trip.start_date - timedelta(days=date_tolerance_days)
        window_end   = trip.end_date   + timedelta(days=date_tolerance_days)

        date_match = any(window_start <= d <= window_end for d in expense_dates)
        if date_match:
            return trip

    return None


def find_trip_by_date_window(
    employee_id: str,
    check_date: date,
    db: Session,
    tolerance_days: int = 1,
) -> Trip | None:
    """
    Find a trip whose date window (with tolerance) contains check_date.
    Used as a fallback in trip matching when the primary criteria fail
    but a card transaction date can be used to infer the trip.
    """
    active_trips = get_active_trips_for_employee(employee_id, db)
    for trip in active_trips:
        window_start = trip.start_date - timedelta(days=tolerance_days)
        window_end   = trip.end_date   + timedelta(days=tolerance_days)
        if window_start <= check_date <= window_end:
            return trip
    return None


def update_status(trip_id: str, status: str, db: Session) -> None:
    trip = db.get(Trip, trip_id)
    if trip:
        trip.status = status
        db.flush()
