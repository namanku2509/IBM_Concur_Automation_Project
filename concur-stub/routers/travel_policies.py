"""
routers/travel_policies.py
---------------------------
GET /api/v4/travel-policies/{name}

Returns a travel policy and all its rules.
Layer 2 uses this to understand the limits before building expense payloads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.travel_policy import TravelPolicy
from schemas.common import ErrorResponse, ErrorCode
from schemas.travel_policy import PolicyRuleResponse, TravelPolicyResponse

router = APIRouter(tags=["travel-policies"])


@router.get(
    "/travel-policies/{policy_name}",
    response_model=TravelPolicyResponse,
    summary="Get travel policy with all rules",
    responses={404: {"model": ErrorResponse, "description": "Policy not found"}},
)
def get_travel_policy(
    policy_name: str,
    db: Session = Depends(get_db),
) -> TravelPolicyResponse:
    """
    Retrieve a named travel policy including all its expense rules.
    The AI layer uses this to understand limits (hotel nightly caps, meal limits, etc.)
    before building expense submission payloads.
    """
    policy = db.get(TravelPolicy, policy_name.upper())
    if not policy:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_FOUND,  # reuse generic error
                message=f"Travel policy {policy_name!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    return TravelPolicyResponse(
        name=policy.name,
        description=policy.description,
        rules=[
            PolicyRuleResponse(
                id=rule.id,
                expense_type=rule.expense_type,
                rule_key=rule.rule_key,
                rule_value=rule.rule_value,
                currency=rule.currency,
            )
            for rule in policy.rules
        ],
        created_at=policy.created_at,
    )
