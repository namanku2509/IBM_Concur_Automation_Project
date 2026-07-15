"""
models/travel_policy.py
------------------------
SQLAlchemy ORM models for `travel_policies` and `policy_rules` tables.

Travel policies are first-class entities. Each employee is assigned to
exactly one named policy. Policy rules are stored as key-value rows
so that limits can be changed via SQL without restarting the server.

Design:
  travel_policies  (1) ──── (N)  policy_rules
  travel_policies  (1) ──── (N)  employees
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TravelPolicy(Base):
    __tablename__ = "travel_policies"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    """Human-readable identifier, e.g. 'STANDARD', 'EXECUTIVE'."""

    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    rules: Mapped[list["PolicyRule"]] = relationship(
        "PolicyRule", back_populates="travel_policy", cascade="all, delete-orphan"
    )
    employees: Mapped[list["Employee"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Employee", back_populates="travel_policy"
    )

    def __repr__(self) -> str:
        return f"<TravelPolicy name={self.name!r}>"


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_name: Mapped[str] = mapped_column(
        String,
        ForeignKey("travel_policies.name", ondelete="CASCADE"),
        nullable=False,
    )
    expense_type: Mapped[str] = mapped_column(String, nullable=False)
    """
    The expense type this rule applies to.
    Use 'ALL' for rules that apply to every expense type.
    Valid values: HOTEL | MEAL | TAXI | FLIGHT | ALL
    """

    rule_key: Mapped[str] = mapped_column(String, nullable=False)
    """
    The identifier for this rule, e.g. NIGHTLY_LIMIT, MEAL_LIMIT,
    MAX_TRAVEL_CLASS, ALLOWED_CURRENCIES, ALLOWED_PAYMENT_TYPES,
    OCR_CONFIDENCE_THRESHOLD.
    """

    rule_value: Mapped[str] = mapped_column(String, nullable=False)
    """
    JSON-serialized value. Can be a number (e.g. '6000'), a string
    (e.g. '"ECONOMY"'), or a list (e.g. '["INR","USD"]').
    The policy engine deserializes this with json.loads().
    """

    currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    """
    Context currency for monetary limits (e.g. 'INR').
    NULL for non-monetary rules like MAX_TRAVEL_CLASS.
    """

    # Relationship
    travel_policy: Mapped["TravelPolicy"] = relationship(
        "TravelPolicy", back_populates="rules"
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyRule policy={self.policy_name!r} "
            f"type={self.expense_type!r} key={self.rule_key!r} value={self.rule_value!r}>"
        )
