"""
tests/test_policy_engine.py
----------------------------
Unit tests for every PolicyValidator in services/policy_engine.py.

All validators are tested in complete isolation — no database session
is required. Each test constructs an ExpenseInput and a RuleBag directly.

Test coverage:
  HotelNightlyLimitValidator  — room rate above/below/equal to limit
  MealLimitValidator          — amount above/below limit
  TravelClassValidator        — BUSINESS vs ECONOMY limits
  PaymentTypeValidator        — personal cash advisory
  OcrConfidenceValidator      — below threshold / absent / above threshold
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

import pytest

from schemas.common import WarningCode
from schemas.expense import (
    AirfareDetailInput,
    ExpenseInput,
    HotelItemizationInput,
    MealDetailInput,
)
from services.policy_engine import (
    HotelNightlyLimitValidator,
    MealLimitValidator,
    OcrConfidenceValidator,
    PaymentTypeValidator,
    RuleBag,
    TravelClassValidator,
)


# ------------------------------------------------------------------ #
# Helper factories                                                     #
# ------------------------------------------------------------------ #

def _hotel_expense(
    room_rates: List[float],
    amount: Optional[float] = None,
    currency: str = "INR",
) -> ExpenseInput:
    itemization = [
        HotelItemizationInput(
            night_date=date(2026, 7, 20 + i),
            room_rate=r,
            taxes=r * 0.18,
            incidentals=100.0,
        )
        for i, r in enumerate(room_rates)
    ]
    total = amount if amount is not None else sum(
        r + r * 0.18 + 100.0 for r in room_rates
    )
    return ExpenseInput(
        expense_type="HOTEL",
        vendor="Marriott",
        amount=total,
        currency=currency,
        transaction_date=date(2026, 7, 20),
        city="Bengaluru",
        payment_type="CORPORATE_CARD",
        itemization=itemization,
    )


def _meal_expense(amount: float, currency: str = "INR") -> ExpenseInput:
    return ExpenseInput(
        expense_type="MEAL",
        vendor="Test Restaurant",
        amount=amount,
        currency=currency,
        transaction_date=date(2026, 7, 21),
        city="Bengaluru",
        payment_type="PERSONAL_CASH",
        meal_detail=MealDetailInput(meal_type="LUNCH", attendees=1),
    )


def _flight_expense(travel_class: str) -> ExpenseInput:
    return ExpenseInput(
        expense_type="FLIGHT",
        vendor="IndiGo Airlines",
        amount=5500.0,
        currency="INR",
        transaction_date=date(2026, 7, 19),
        city="Bengaluru",
        payment_type="CORPORATE_CARD",
        airfare_detail=AirfareDetailInput(
            origin="Mumbai",
            destination="Bengaluru",
            travel_class=travel_class,
        ),
    )


def _taxi_expense(payment_type: str = "PERSONAL_CASH", ocr_confidence: Optional[float] = None) -> ExpenseInput:
    return ExpenseInput(
        expense_type="TAXI",
        vendor="Ola",
        amount=650.0,
        currency="INR",
        transaction_date=date(2026, 7, 21),
        city="Bengaluru",
        payment_type=payment_type,
        ocr_confidence=ocr_confidence,
    )


# ------------------------------------------------------------------ #
# HotelNightlyLimitValidator                                          #
# ------------------------------------------------------------------ #

class TestHotelNightlyLimitValidator:
    def test_no_warning_when_rate_below_limit(self):
        expense = _hotel_expense(room_rates=[5000.0])
        rules   = RuleBag(values={"NIGHTLY_LIMIT": 6000.0})
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_rate_equals_limit(self):
        expense = _hotel_expense(room_rates=[6000.0])
        rules   = RuleBag(values={"NIGHTLY_LIMIT": 6000.0})
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert result == []

    def test_warning_when_single_night_exceeds_limit(self):
        expense = _hotel_expense(room_rates=[7500.0])
        rules   = RuleBag(values={"NIGHTLY_LIMIT": 6000.0})
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert len(result) == 1
        assert result[0].code == WarningCode.HOTEL_NIGHTLY_LIMIT_EXCEEDED
        assert "7,500.00" in result[0].message
        assert "6,000.00" in result[0].message

    def test_warning_per_night_not_per_expense(self):
        """Each night that exceeds the limit produces its own warning."""
        expense = _hotel_expense(room_rates=[7500.0, 5000.0, 8000.0])
        rules   = RuleBag(values={"NIGHTLY_LIMIT": 6000.0})
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert len(result) == 2  # night 1 (7500) and night 3 (8000) exceed 6000

    def test_no_warning_when_rule_absent(self):
        expense = _hotel_expense(room_rates=[99000.0])
        rules   = RuleBag(values={})   # no NIGHTLY_LIMIT rule
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_for_non_hotel_expense(self):
        expense = _meal_expense(amount=1500.0)
        rules   = RuleBag(values={"NIGHTLY_LIMIT": 6000.0})
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_itemization_absent(self):
        """Edge case: HOTEL expense with no itemization list."""
        expense = _hotel_expense(room_rates=[7500.0])
        expense = expense.model_copy(update={"itemization": None})
        rules   = RuleBag(values={"NIGHTLY_LIMIT": 6000.0})
        result  = HotelNightlyLimitValidator().validate(expense, rules)
        assert result == []


# ------------------------------------------------------------------ #
# MealLimitValidator                                                   #
# ------------------------------------------------------------------ #

class TestMealLimitValidator:
    def test_no_warning_when_amount_below_limit(self):
        expense = _meal_expense(amount=800.0)
        rules   = RuleBag(values={"MEAL_LIMIT": 1000.0})
        result  = MealLimitValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_amount_equals_limit(self):
        expense = _meal_expense(amount=1000.0)
        rules   = RuleBag(values={"MEAL_LIMIT": 1000.0})
        result  = MealLimitValidator().validate(expense, rules)
        assert result == []

    def test_warning_when_amount_exceeds_limit(self):
        expense = _meal_expense(amount=1500.0)
        rules   = RuleBag(values={"MEAL_LIMIT": 1000.0})
        result  = MealLimitValidator().validate(expense, rules)
        assert len(result) == 1
        assert result[0].code == WarningCode.MEAL_LIMIT_EXCEEDED
        assert "1,500.00" in result[0].message

    def test_no_warning_when_rule_absent(self):
        expense = _meal_expense(amount=99999.0)
        rules   = RuleBag(values={})
        result  = MealLimitValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_for_non_meal_expense(self):
        expense = _hotel_expense(room_rates=[5000.0])
        rules   = RuleBag(values={"MEAL_LIMIT": 1000.0})
        result  = MealLimitValidator().validate(expense, rules)
        assert result == []


# ------------------------------------------------------------------ #
# TravelClassValidator                                                 #
# ------------------------------------------------------------------ #

class TestTravelClassValidator:
    def test_no_warning_economy_under_economy_policy(self):
        expense = _flight_expense("ECONOMY")
        rules   = RuleBag(values={"MAX_TRAVEL_CLASS": "ECONOMY"})
        result  = TravelClassValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_business_under_business_policy(self):
        expense = _flight_expense("BUSINESS")
        rules   = RuleBag(values={"MAX_TRAVEL_CLASS": "BUSINESS"})
        result  = TravelClassValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_economy_under_business_policy(self):
        expense = _flight_expense("ECONOMY")
        rules   = RuleBag(values={"MAX_TRAVEL_CLASS": "BUSINESS"})
        result  = TravelClassValidator().validate(expense, rules)
        assert result == []

    def test_warning_business_under_economy_policy(self):
        """Core scenario: STANDARD policy employee booking business class."""
        expense = _flight_expense("BUSINESS")
        rules   = RuleBag(values={"MAX_TRAVEL_CLASS": "ECONOMY"})
        result  = TravelClassValidator().validate(expense, rules)
        assert len(result) == 1
        assert result[0].code == WarningCode.TRAVEL_CLASS_VIOLATION
        assert "BUSINESS" in result[0].message
        assert "ECONOMY" in result[0].message

    def test_no_warning_when_rule_absent(self):
        expense = _flight_expense("BUSINESS")
        rules   = RuleBag(values={})
        result  = TravelClassValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_no_airfare_detail(self):
        expense = _flight_expense("BUSINESS")
        expense = expense.model_copy(update={"airfare_detail": None})
        rules   = RuleBag(values={"MAX_TRAVEL_CLASS": "ECONOMY"})
        result  = TravelClassValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_for_non_flight_expense(self):
        expense = _meal_expense(amount=500.0)
        rules   = RuleBag(values={"MAX_TRAVEL_CLASS": "ECONOMY"})
        result  = TravelClassValidator().validate(expense, rules)
        assert result == []


# ------------------------------------------------------------------ #
# PaymentTypeValidator                                                 #
# ------------------------------------------------------------------ #

class TestPaymentTypeValidator:
    def test_no_warning_corporate_card(self):
        expense = _taxi_expense(payment_type="CORPORATE_CARD")
        rules   = RuleBag(values={"ALLOWED_PAYMENT_TYPES": ["CORPORATE_CARD", "PERSONAL_CASH"]})
        result  = PaymentTypeValidator().validate(expense, rules)
        assert result == []

    def test_info_warning_personal_cash(self):
        """Personal cash is allowed but an advisory INFO warning is emitted."""
        expense = _taxi_expense(payment_type="PERSONAL_CASH")
        rules   = RuleBag(values={"ALLOWED_PAYMENT_TYPES": ["CORPORATE_CARD", "PERSONAL_CASH"]})
        result  = PaymentTypeValidator().validate(expense, rules)
        assert len(result) == 1
        assert result[0].code == WarningCode.PAYMENT_TYPE_ADVISORY
        from schemas.common import WarningSeverity
        assert result[0].severity == WarningSeverity.INFO

    def test_no_warning_when_rule_absent(self):
        expense = _taxi_expense(payment_type="PERSONAL_CASH")
        rules   = RuleBag(values={})
        result  = PaymentTypeValidator().validate(expense, rules)
        assert result == []


# ------------------------------------------------------------------ #
# OcrConfidenceValidator                                               #
# ------------------------------------------------------------------ #

class TestOcrConfidenceValidator:
    def test_no_warning_when_confidence_absent(self):
        """Graceful skip — Layer 2 did not include ocrConfidence."""
        expense = _taxi_expense(ocr_confidence=None)
        rules   = RuleBag(values={"OCR_CONFIDENCE_THRESHOLD": 0.75})
        result  = OcrConfidenceValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_rule_absent(self):
        expense = _taxi_expense(ocr_confidence=0.50)
        rules   = RuleBag(values={})
        result  = OcrConfidenceValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_confidence_meets_threshold(self):
        expense = _taxi_expense(ocr_confidence=0.80)
        rules   = RuleBag(values={"OCR_CONFIDENCE_THRESHOLD": 0.75})
        result  = OcrConfidenceValidator().validate(expense, rules)
        assert result == []

    def test_no_warning_when_confidence_equals_threshold(self):
        expense = _taxi_expense(ocr_confidence=0.75)
        rules   = RuleBag(values={"OCR_CONFIDENCE_THRESHOLD": 0.75})
        result  = OcrConfidenceValidator().validate(expense, rules)
        assert result == []

    def test_warning_when_confidence_below_threshold(self):
        expense = _taxi_expense(ocr_confidence=0.60)
        rules   = RuleBag(values={"OCR_CONFIDENCE_THRESHOLD": 0.75})
        result  = OcrConfidenceValidator().validate(expense, rules)
        assert len(result) == 1
        assert result[0].code == WarningCode.LOW_OCR_CONFIDENCE
        assert "60%" in result[0].message
        assert "75%" in result[0].message
