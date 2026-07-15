"""
schemas/employee.py
--------------------
Pydantic v2 schemas for the Employee domain.

GET /api/v4/employees/{id} returns EmployeeResponse.
No POST/PATCH — employees are managed via seed data and admin tools.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeeResponse(BaseModel):
    """
    Employee profile returned to Layer 2.
    Includes travel_policy_name so the AI middleware knows which
    policy to reference when building the expense report payload.
    """
    model_config = ConfigDict(populate_by_name=True)

    employee_id: str = Field(
        ...,
        alias="employeeId",
        description="Unique employee identifier",
        examples=["EMP001"],
    )
    name: str = Field(..., examples=["Priya Sharma"])
    email: str = Field(..., examples=["priya.sharma@ibmclient.com"])
    travel_policy_name: str = Field(
        ...,
        alias="travelPolicyName",
        description="Name of the travel policy assigned to this employee",
        examples=["STANDARD"],
    )
    department: str = Field(..., examples=["Consulting"])
    manager_id: Optional[str] = Field(
        default=None,
        alias="managerId",
        examples=["EMP003"],
    )
    is_active: bool = Field(..., alias="isActive")
    created_at: datetime = Field(..., alias="createdAt")
