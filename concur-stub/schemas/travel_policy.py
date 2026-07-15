"""
schemas/travel_policy.py
-------------------------
Pydantic v2 schemas for the TravelPolicy and PolicyRule domains.

GET /api/v4/travel-policies/{name} returns TravelPolicyResponse,
which includes all rules for that policy. Layer 2 uses this to
understand the limits before building expense payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PolicyRuleResponse(BaseModel):
    """A single policy rule row returned as part of a policy response."""
    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(..., description="Rule ID")
    expense_type: str = Field(
        ...,
        alias="expenseType",
        description="Expense type this rule applies to, or ALL",
        examples=["HOTEL"],
    )
    rule_key: str = Field(
        ...,
        alias="ruleKey",
        description="The rule identifier",
        examples=["NIGHTLY_LIMIT"],
    )
    rule_value: str = Field(
        ...,
        alias="ruleValue",
        description="JSON-serialized value of the rule",
        examples=["6000"],
    )
    currency: Optional[str] = Field(
        default=None,
        description="Context currency for monetary limits",
        examples=["INR"],
    )


class TravelPolicyResponse(BaseModel):
    """Full travel policy including all its rules."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., examples=["STANDARD"])
    description: str = Field(
        ...,
        examples=["Standard domestic travel policy for all employees"],
    )
    rules: list[PolicyRuleResponse] = Field(
        default_factory=list,
        description="All policy rules for this travel policy",
    )
    created_at: datetime = Field(..., alias="createdAt")
