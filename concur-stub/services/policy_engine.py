"""
services/policy_engine.py
--------------------------
Composable policy validation engine.

Architecture:
  - PolicyValidator: abstract base class — one subclass per rule type
  - PolicyEngine: orchestrator that loads rules from DB and runs validators
  - run_policy_checks(): the single public entry point called by expense_service

Design constraints (from the plan):
  1. The engine NEVER raises HTTP exceptions or returns PreflightErrors.
     It returns list[ValidationWarning] only.
  2. Rules are loaded fresh from SQLite on every invocation — no caching —
     so a policy change (e.g. raising a hotel limit) takes effect immediately
     without restarting the server.
  3. Each validator is independently testable with no DB dependency.
  4. New rules are added by creating a new PolicyValidator subclass and
     registering it in PolicyEngine._validators — no changes elsewhere.

Validator registry:
  HOTEL  → HotelNightlyLimitValidator
  MEAL   → MealLimitValidator
  FLIGHT → TravelClassValidator
  ALL    → PaymentTypeValidator, OcrConfidenceValidator
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.travel_policy import PolicyRule
from schemas.common import ValidationWarning, WarningCode, WarningSeverity
from schemas.expense import ExpenseInput

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Rule bag — passed to each validator                                  #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class RuleBag:
    """
    Parsed rules for a single (policy_name, expense_type) combination.
    Values are already deserialized from JSON for convenience.

    Attributes keyed by rule_key, e.g.:
        rules["NIGHTLY_LIMIT"] = 6000.0
        rules["ALLOWED_CURRENCIES"] = ["INR"]
        rules["MAX_TRAVEL_CLASS"] = "ECONOMY"
    """
    values: dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.values


def _load_rule_bag(
    policy_name: str,
    expense_type: str,
    db: Session,
) -> RuleBag:
    """
    Load all rules for (policy_name, expense_type) UNION (policy_name, ALL).
    Returns a RuleBag with deserialized values.
    """
    rows: list[PolicyRule] = (
        db.query(PolicyRule)
        .filter(
            PolicyRule.policy_name == policy_name,
            PolicyRule.expense_type.in_([expense_type, "ALL"]),
        )
        .all()
    )
    values: dict[str, Any] = {}
    for row in rows:
        try:
            values[row.rule_key] = json.loads(row.rule_value)
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "Could not parse policy rule value: policy=%s key=%s value=%r",
                policy_name,
                row.rule_key,
                row.rule_value,
            )
    return RuleBag(values=values)


# ------------------------------------------------------------------ #
# Abstract base                                                        #
# ------------------------------------------------------------------ #

class PolicyValidator(ABC):
    """
    Abstract base for all policy validators.

    Each subclass encapsulates a single validation concern.
    The validate() method receives the expense and the pre-loaded RuleBag,
    making it fully testable without a DB session.
    """

    @abstractmethod
    def validate(
        self,
        expense: ExpenseInput,
        rules: RuleBag,
    ) -> list[ValidationWarning]:
        """
        Run this validator against a single expense.
        Returns a (possibly empty) list of ValidationWarning objects.
        Must never raise exceptions — catch defensively and return [].
        """
        ...

    def _warn(
        self,
        code: WarningCode,
        message: str,
        field: Optional[str] = None,
        severity: WarningSeverity = WarningSeverity.WARNING,
    ) -> ValidationWarning:
        return ValidationWarning(
            code=code,
            message=message,
            severity=severity,
            field=field,
        )


# ------------------------------------------------------------------ #
# Concrete validators                                                  #
# ------------------------------------------------------------------ #

class HotelNightlyLimitValidator(PolicyValidator):
    """
    Warns when any itemization line's room_rate exceeds the NIGHTLY_LIMIT
    rule for the employee's travel policy.

    Applies to: HOTEL expenses only.
    Rule key:   NIGHTLY_LIMIT (numeric, in policy currency)
    """

    def validate(self, expense: ExpenseInput, rules: RuleBag) -> list[ValidationWarning]:
        if expense.expense_type.value != "HOTEL":
            return []
        if "NIGHTLY_LIMIT" not in rules:
            return []
        if not expense.itemization:
            return []

        try:
            limit = float(rules.get("NIGHTLY_LIMIT"))
        except (TypeError, ValueError):
            logger.warning("NIGHTLY_LIMIT rule value is not numeric")
            return []

        warnings: list[ValidationWarning] = []
        for line in expense.itemization:
            if line.room_rate > limit:
                warnings.append(
                    self._warn(
                        code=WarningCode.HOTEL_NIGHTLY_LIMIT_EXCEEDED,
                        message=(
                            f"Nightly room rate {expense.currency} {line.room_rate:,.2f} "
                            f"on {line.night_date} exceeds policy limit "
                            f"{expense.currency} {limit:,.2f}"
                        ),
                        field="roomRate",
                    )
                )
        return warnings


class MealLimitValidator(PolicyValidator):
    """
    Warns when a MEAL expense amount exceeds the MEAL_LIMIT rule.

    Applies to: MEAL expenses only.
    Rule key:   MEAL_LIMIT (numeric)
    """

    def validate(self, expense: ExpenseInput, rules: RuleBag) -> list[ValidationWarning]:
        if expense.expense_type.value != "MEAL":
            return []
        if "MEAL_LIMIT" not in rules:
            return []

        try:
            limit = float(rules.get("MEAL_LIMIT"))
        except (TypeError, ValueError):
            logger.warning("MEAL_LIMIT rule value is not numeric")
            return []

        if expense.amount > limit:
            return [
                self._warn(
                    code=WarningCode.MEAL_LIMIT_EXCEEDED,
                    message=(
                        f"Meal amount {expense.currency} {expense.amount:,.2f} "
                        f"exceeds policy limit {expense.currency} {limit:,.2f}"
                    ),
                    field="amount",
                )
            ]
        return []


class TravelClassValidator(PolicyValidator):
    """
    Warns when a FLIGHT expense uses a travel class that exceeds the
    MAX_TRAVEL_CLASS allowed by the employee's policy.

    Class hierarchy: ECONOMY < BUSINESS
    Applies to: FLIGHT expenses with airfareDetail present.
    Rule key:   MAX_TRAVEL_CLASS (string: "ECONOMY" or "BUSINESS")
    """

    _CLASS_RANK: dict[str, int] = {"ECONOMY": 1, "BUSINESS": 2}

    def validate(self, expense: ExpenseInput, rules: RuleBag) -> list[ValidationWarning]:
        if expense.expense_type.value != "FLIGHT":
            return []
        if not expense.airfare_detail:
            return []
        if "MAX_TRAVEL_CLASS" not in rules:
            return []

        max_class: str = str(rules.get("MAX_TRAVEL_CLASS", "ECONOMY")).upper()
        actual_class: str = expense.airfare_detail.travel_class.value.upper()

        max_rank    = self._CLASS_RANK.get(max_class, 1)
        actual_rank = self._CLASS_RANK.get(actual_class, 1)

        if actual_rank > max_rank:
            return [
                self._warn(
                    code=WarningCode.TRAVEL_CLASS_VIOLATION,
                    message=(
                        f"Travel class {actual_class!r} exceeds the maximum "
                        f"allowed class {max_class!r} for this travel policy"
                    ),
                    field="travelClass",
                )
            ]
        return []


class PaymentTypeValidator(PolicyValidator):
    """
    Warns when an expense uses PERSONAL_CASH payment when the policy
    expects CORPORATE_CARD to be used (advisory — not a hard block).

    Applies to: ALL expense types.
    Rule key:   ALLOWED_PAYMENT_TYPES (list of strings)
    """

    def validate(self, expense: ExpenseInput, rules: RuleBag) -> list[ValidationWarning]:
        if "ALLOWED_PAYMENT_TYPES" not in rules:
            return []

        allowed: list[str] = rules.get("ALLOWED_PAYMENT_TYPES", [])
        payment_type = expense.payment_type.value

        if payment_type not in allowed:
            return [
                self._warn(
                    code=WarningCode.PAYMENT_TYPE_ADVISORY,
                    message=(
                        f"Payment type {payment_type!r} is not in the list of "
                        f"preferred payment types: {allowed}. "
                        "Please use a corporate card where possible."
                    ),
                    field="paymentType",
                    severity=WarningSeverity.INFO,
                )
            ]

        # Advisory: personal cash is technically allowed but preferred
        # to use corporate card — generate a soft INFO warning
        if payment_type == "PERSONAL_CASH" and "CORPORATE_CARD" in allowed:
            return [
                self._warn(
                    code=WarningCode.PAYMENT_TYPE_ADVISORY,
                    message=(
                        "Personal cash was used for this expense. "
                        "Company policy prefers payment via corporate card "
                        "to simplify reconciliation."
                    ),
                    field="paymentType",
                    severity=WarningSeverity.INFO,
                )
            ]
        return []


class OcrConfidenceValidator(PolicyValidator):
    """
    Warns when the OCR confidence score passed by Layer 2 is below the
    threshold defined in the policy's OCR_CONFIDENCE_THRESHOLD rule.

    Silently skips if ocrConfidence is absent from the expense payload —
    the field is optional and older Layer 2 versions may not send it.

    Applies to: ALL expense types.
    Rule key:   OCR_CONFIDENCE_THRESHOLD (float 0.0–1.0)
    """

    def validate(self, expense: ExpenseInput, rules: RuleBag) -> list[ValidationWarning]:
        # Gracefully skip if Layer 2 did not include OCR confidence
        if expense.ocr_confidence is None:
            return []
        if "OCR_CONFIDENCE_THRESHOLD" not in rules:
            return []

        try:
            threshold = float(rules.get("OCR_CONFIDENCE_THRESHOLD"))
        except (TypeError, ValueError):
            return []

        if expense.ocr_confidence < threshold:
            return [
                self._warn(
                    code=WarningCode.LOW_OCR_CONFIDENCE,
                    message=(
                        f"OCR confidence {expense.ocr_confidence:.0%} is below "
                        f"the policy threshold of {threshold:.0%}. "
                        "Please verify all extracted fields manually."
                    ),
                    field="ocrConfidence",
                    severity=WarningSeverity.WARNING,
                )
            ]
        return []


# ------------------------------------------------------------------ #
# Engine orchestrator                                                  #
# ------------------------------------------------------------------ #

class PolicyEngine:
    """
    Orchestrates all validators for a given expense.

    Usage:
        engine = PolicyEngine(db)
        warnings = engine.run(expense, policy_name)
    """

    # Validator registry: maps expense_type (or "ALL") to validator classes.
    # Order within each list determines warning output order.
    _validators: dict[str, list[type[PolicyValidator]]] = {
        "HOTEL":  [HotelNightlyLimitValidator],
        "MEAL":   [MealLimitValidator],
        "FLIGHT": [TravelClassValidator],
        "TAXI":   [],
        "ALL":    [PaymentTypeValidator, OcrConfidenceValidator],
    }

    def __init__(self, db: Session) -> None:
        self._db = db

    def run(
        self,
        expense: ExpenseInput,
        policy_name: str,
    ) -> list[ValidationWarning]:
        """
        Run all applicable validators for this expense against the
        given travel policy. Returns the aggregated list of warnings.
        """
        expense_type = expense.expense_type.value
        rules = _load_rule_bag(policy_name, expense_type, self._db)

        all_warnings: list[ValidationWarning] = []

        # Type-specific validators
        for validator_cls in self._validators.get(expense_type, []):
            try:
                all_warnings.extend(validator_cls().validate(expense, rules))
            except Exception:
                logger.exception(
                    "Validator %s raised an unexpected exception for expense type %s",
                    validator_cls.__name__,
                    expense_type,
                )

        # Universal validators (ALL)
        for validator_cls in self._validators.get("ALL", []):
            try:
                all_warnings.extend(validator_cls().validate(expense, rules))
            except Exception:
                logger.exception(
                    "Validator %s raised an unexpected exception",
                    validator_cls.__name__,
                )

        return all_warnings


# ------------------------------------------------------------------ #
# Public entry point                                                   #
# ------------------------------------------------------------------ #

def run_policy_checks(
    expense: ExpenseInput,
    policy_name: str,
    db: Session,
) -> list[ValidationWarning]:
    """
    Main entry point called by expense_service.py (Step 7).

    Instantiates a PolicyEngine and runs all applicable validators.
    Returns the aggregated list of ValidationWarning objects.
    Never raises — all exceptions are caught inside the engine.
    """
    return PolicyEngine(db).run(expense, policy_name)
