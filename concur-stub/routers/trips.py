"""
routers/trips.py
-----------------
POST /api/v4/trips
GET  /api/v4/trips/{tripId}
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.trip import Trip
from repositories import trip_repo, employee_repo
from schemas.common import ErrorCode, ErrorResponse
from schemas.trip import TripCreate, TripResponse

router = APIRouter(tags=["trips"])


@router.post(
    "/trips",
    response_model=TripResponse,
    status_code=201,
    summary="Create a new business trip",
)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
) -> TripResponse:
    """
    Register a new business trip. Used by the Trip Planner Agent in Layer 3.
    The trip record is later used for expense report matching (Step 5).
    """
    # Validate employee exists
    if not employee_repo.get_by_id(payload.employee_id, db):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {payload.employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )

    trip = Trip(
        id=payload.trip_id,
        employee_id=payload.employee_id,
        destination_city=payload.destination_city,
        start_date=payload.start_date,
        end_date=payload.end_date,
        purpose=payload.purpose,
        status=payload.status.value,
    )
    trip_repo.create(trip, db)
    db.commit()

    return TripResponse(
        trip_id=trip.id,
        employee_id=trip.employee_id,
        destination_city=trip.destination_city,
        start_date=trip.start_date,
        end_date=trip.end_date,
        purpose=trip.purpose,
        status=trip.status,
        created_at=trip.created_at,
    )


@router.get(
    "/trips/{trip_id}",
    response_model=TripResponse,
    summary="Get a trip by ID",
    responses={404: {"model": ErrorResponse}},
)
def get_trip(
    trip_id: str,
    db: Session = Depends(get_db),
) -> TripResponse:
    trip = trip_repo.get_by_id(trip_id, db)
    if not trip:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_FOUND,
                message=f"Trip {trip_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    return TripResponse(
        trip_id=trip.id,
        employee_id=trip.employee_id,
        destination_city=trip.destination_city,
        start_date=trip.start_date,
        end_date=trip.end_date,
        purpose=trip.purpose,
        status=trip.status,
        created_at=trip.created_at,
    )
