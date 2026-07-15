"""
schemas/trip.py
---------------
Pydantic v2 schemas for the Trip domain.

POST /api/v4/trips        → TripCreate  (request)  → TripResponse (response)
GET  /api/v4/trips/{id}   →                          TripResponse (response)
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import TripStatus


class TripCreate(BaseModel):
    """Request body for creating a new trip."""
    model_config = ConfigDict(populate_by_name=True)

    trip_id: str = Field(
        ...,
        alias="tripId",
        description="Client-supplied trip ID. Must be unique.",
        examples=["TRIP001"],
    )
    employee_id: str = Field(
        ...,
        alias="employeeId",
        examples=["EMP001"],
    )
    destination_city: str = Field(
        ...,
        alias="destinationCity",
        examples=["Bengaluru"],
    )
    start_date: date = Field(
        ...,
        alias="startDate",
        examples=["2026-07-20"],
    )
    end_date: date = Field(
        ...,
        alias="endDate",
        examples=["2026-07-23"],
    )
    purpose: str = Field(
        ...,
        examples=["Client workshop — IBM Garage"],
    )
    status: TripStatus = Field(
        default=TripStatus.ACTIVE,
    )


class TripResponse(BaseModel):
    """Trip record returned to the caller."""
    model_config = ConfigDict(populate_by_name=True)

    trip_id: str = Field(..., alias="tripId", examples=["TRIP001"])
    employee_id: str = Field(..., alias="employeeId", examples=["EMP001"])
    destination_city: str = Field(..., alias="destinationCity", examples=["Bengaluru"])
    start_date: date = Field(..., alias="startDate")
    end_date: date = Field(..., alias="endDate")
    purpose: str
    status: TripStatus
    created_at: datetime = Field(..., alias="createdAt")
