"""
routers/employees.py
---------------------
GET /api/v4/employees/{employeeId}

Returns the employee profile including their travel policy name.
Layer 2 calls this to resolve the policy before building expense payloads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories import employee_repo
from schemas.common import ErrorCode, ErrorResponse
from schemas.employee import EmployeeResponse

router = APIRouter(tags=["employees"])


@router.get(
    "/employees/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get employee profile",
    responses={
        404: {"model": ErrorResponse, "description": "Employee not found"},
    },
)
def get_employee(
    employee_id: str,
    db: Session = Depends(get_db),
) -> EmployeeResponse:
    """
    Retrieve an employee's profile including their assigned travel policy name.
    Layer 2 uses this to resolve which policy rules apply before submitting expenses.
    """
    emp = employee_repo.get_by_id(employee_id, db)
    if not emp:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    return EmployeeResponse(
        employee_id=emp.id,
        name=emp.name,
        email=emp.email,
        travel_policy_name=emp.travel_policy_name,
        department=emp.department,
        manager_id=emp.manager_id,
        is_active=emp.is_active,
        created_at=emp.created_at,
    )
