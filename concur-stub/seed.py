from __future__ import annotations

"""
seed.py
-------
Populates the SQLite database with reference data required for all four
demo scenarios. Called from main.py lifespan on every startup.

Idempotency guarantee:
    The function checks whether `travel_policies` already has rows.
    If yes, it exits immediately. This means re-running the server
    never creates duplicate seed data.

Seed inventory:
    Travel Policies:  STANDARD, EXECUTIVE
    Policy Rules:     Per-policy limits for HOTEL, MEAL, FLIGHT, ALL
    Employees:        EMP001–EMP004 across both policies and 4 cities
    Trips:            One ACTIVE trip per employee, 4 Indian cities
    Card Transactions: 5–8 per employee, covering HOTEL/FLIGHT/TAXI/MEAL
                       Includes intentional non-matches for pipeline testing

Demo scenarios enabled by this seed data:
    1. Happy path       — EMP001 Bengaluru trip, all cards match, no warnings
    2. Policy violation — EMP002 hotel exceeds STANDARD 6000 INR limit
    3. Unmatched trip   — Submit expenses with no matching trip record
    4. Duplicate detect — Re-submit same expense for EMP001
"""

from datetime import date

from sqlalchemy.orm import Session

from database import SessionLocal
from models.travel_policy import PolicyRule, TravelPolicy
from models.employee import Employee
from models.trip import Trip
from models.corporate_card_transaction import CorporateCardTransaction


# ------------------------------------------------------------------ #
# Policy rule constants                                                #
# ------------------------------------------------------------------ #

_STANDARD_RULES = [
    # HOTEL
    dict(expense_type="HOTEL", rule_key="NIGHTLY_LIMIT",        rule_value="6000",            currency="INR"),
    # MEAL
    dict(expense_type="MEAL",  rule_key="MEAL_LIMIT",            rule_value="1000",            currency="INR"),
    # FLIGHT
    dict(expense_type="FLIGHT",rule_key="MAX_TRAVEL_CLASS",      rule_value='"ECONOMY"',       currency=None),
    # ALL
    dict(expense_type="ALL",   rule_key="ALLOWED_CURRENCIES",    rule_value='["INR"]',         currency=None),
    dict(expense_type="ALL",   rule_key="ALLOWED_PAYMENT_TYPES", rule_value='["CORPORATE_CARD","PERSONAL_CASH","CORPORATE_CASH"]', currency=None),
    dict(expense_type="ALL",   rule_key="OCR_CONFIDENCE_THRESHOLD", rule_value="0.75",         currency=None),
]

_EXECUTIVE_RULES = [
    # HOTEL — higher limit for senior staff
    dict(expense_type="HOTEL", rule_key="NIGHTLY_LIMIT",        rule_value="12000",           currency="INR"),
    # MEAL — higher limit
    dict(expense_type="MEAL",  rule_key="MEAL_LIMIT",            rule_value="2500",            currency="INR"),
    # FLIGHT — business class allowed
    dict(expense_type="FLIGHT",rule_key="MAX_TRAVEL_CLASS",      rule_value='"BUSINESS"',      currency=None),
    # ALL — multi-currency for international travel
    dict(expense_type="ALL",   rule_key="ALLOWED_CURRENCIES",    rule_value='["INR","USD","GBP","EUR"]', currency=None),
    dict(expense_type="ALL",   rule_key="ALLOWED_PAYMENT_TYPES", rule_value='["CORPORATE_CARD","PERSONAL_CASH","CORPORATE_CASH"]', currency=None),
    dict(expense_type="ALL",   rule_key="OCR_CONFIDENCE_THRESHOLD", rule_value="0.70",         currency=None),
]


# ------------------------------------------------------------------ #
# Employees                                                            #
# ------------------------------------------------------------------ #

_EMPLOYEES = [
    dict(
        id="EMP001",
        name="Priya Sharma",
        email="priya.sharma@ibmclient.com",
        travel_policy_name="STANDARD",
        department="Consulting",
        manager_id="EMP003",
        is_active=True,
    ),
    dict(
        id="EMP002",
        name="Arjun Mehta",
        email="arjun.mehta@ibmclient.com",
        travel_policy_name="STANDARD",
        department="Engineering",
        manager_id="EMP004",
        is_active=True,
    ),
    dict(
        id="EMP003",
        name="Kavita Nair",
        email="kavita.nair@ibmclient.com",
        travel_policy_name="EXECUTIVE",
        department="Consulting",
        manager_id=None,
        is_active=True,
    ),
    dict(
        id="EMP004",
        name="Rohan Desai",
        email="rohan.desai@ibmclient.com",
        travel_policy_name="EXECUTIVE",
        department="Engineering",
        manager_id=None,
        is_active=True,
    ),
]


# ------------------------------------------------------------------ #
# Trips                                                                #
# ------------------------------------------------------------------ #

_TRIPS = [
    # EMP001 — Bengaluru (used in happy-path demo)
    dict(
        id="TRIP001",
        employee_id="EMP001",
        destination_city="Bengaluru",
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 23),
        purpose="Client workshop — IBM Garage",
        status="ACTIVE",
    ),
    # EMP001 — Mumbai (secondary trip for edge-case testing)
    dict(
        id="TRIP002",
        employee_id="EMP001",
        destination_city="Mumbai",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 12),
        purpose="Partner meeting",
        status="ACTIVE",
    ),
    # EMP002 — Hyderabad (used in policy-violation demo)
    dict(
        id="TRIP003",
        employee_id="EMP002",
        destination_city="Hyderabad",
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 18),
        purpose="Tech conference",
        status="ACTIVE",
    ),
    # EMP003 — Delhi (EXECUTIVE policy, international trip)
    dict(
        id="TRIP004",
        employee_id="EMP003",
        destination_city="Delhi",
        start_date=date(2026, 7, 25),
        end_date=date(2026, 7, 28),
        purpose="Board presentation",
        status="ACTIVE",
    ),
    # EMP004 — Bengaluru (EXECUTIVE policy)
    dict(
        id="TRIP005",
        employee_id="EMP004",
        destination_city="Bengaluru",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 4),
        purpose="Delivery review",
        status="ACTIVE",
    ),
]


# ------------------------------------------------------------------ #
# Corporate card transactions                                          #
# ------------------------------------------------------------------ #
# Notes:
# - CCT001–CCT005: EMP001 Bengaluru trip — designed to match the
#   happy-path demo expenses exactly.
# - CCT006–CCT009: EMP002 Hyderabad trip — hotel CCT matches a
#   7500 INR hotel (exceeds STANDARD 6000 limit → HOTEL warning).
# - CCT010–CCT013: EMP003 Delhi trip (EXECUTIVE — 7500 INR is fine).
# - CCT014: Intentional non-match (wrong amount) for pipeline testing.
# - CCT015–CCT018: EMP004 Bengaluru trip.
# ------------------------------------------------------------------ #

_CARD_TRANSACTIONS = [
    # --- EMP001 Bengaluru (TRIP001: 2026-07-20 to 2026-07-23) ---
    dict(id="CCT001", employee_id="EMP001", vendor="Marriott",         amount=18000.0, currency="INR", transaction_date=date(2026, 7, 20), card_last_four="4242", status="AVAILABLE"),
    dict(id="CCT002", employee_id="EMP001", vendor="IndiGo Airlines",  amount=5500.0,  currency="INR", transaction_date=date(2026, 7, 19), card_last_four="4242", status="AVAILABLE"),
    dict(id="CCT003", employee_id="EMP001", vendor="Ola",              amount=650.0,   currency="INR", transaction_date=date(2026, 7, 20), card_last_four="4242", status="AVAILABLE"),
    dict(id="CCT004", employee_id="EMP001", vendor="The Fatty Bao",    amount=950.0,   currency="INR", transaction_date=date(2026, 7, 21), card_last_four="4242", status="AVAILABLE"),
    dict(id="CCT005", employee_id="EMP001", vendor="Ola",              amount=720.0,   currency="INR", transaction_date=date(2026, 7, 22), card_last_four="4242", status="AVAILABLE"),
    # Intentional non-match: wrong amount — tests CARD_TRANSACTION_NOT_MATCHED
    dict(id="CCT006", employee_id="EMP001", vendor="Uber",             amount=999.0,   currency="INR", transaction_date=date(2026, 7, 21), card_last_four="4242", status="AVAILABLE"),

    # --- EMP002 Hyderabad (TRIP003: 2026-07-15 to 2026-07-18) ---
    # Hotel 7500 INR — exceeds STANDARD NIGHTLY_LIMIT 6000 → HOTEL warning
    dict(id="CCT007", employee_id="EMP002", vendor="Taj Hotels",       amount=15000.0, currency="INR", transaction_date=date(2026, 7, 15), card_last_four="8888", status="AVAILABLE"),
    dict(id="CCT008", employee_id="EMP002", vendor="Air India",        amount=6200.0,  currency="INR", transaction_date=date(2026, 7, 14), card_last_four="8888", status="AVAILABLE"),
    dict(id="CCT009", employee_id="EMP002", vendor="Rapido",           amount=420.0,   currency="INR", transaction_date=date(2026, 7, 15), card_last_four="8888", status="AVAILABLE"),
    dict(id="CCT010", employee_id="EMP002", vendor="Paradise Biryani", amount=800.0,   currency="INR", transaction_date=date(2026, 7, 16), card_last_four="8888", status="AVAILABLE"),
    # Intentional non-match: different vendor — tests CARD_TRANSACTION_NOT_MATCHED
    dict(id="CCT011", employee_id="EMP002", vendor="Unknown Vendor",   amount=500.0,   currency="INR", transaction_date=date(2026, 7, 17), card_last_four="8888", status="AVAILABLE"),

    # --- EMP003 Delhi (TRIP004: 2026-07-25 to 2026-07-28) EXECUTIVE ---
    dict(id="CCT012", employee_id="EMP003", vendor="Leela Palace",     amount=22000.0, currency="INR", transaction_date=date(2026, 7, 25), card_last_four="1111", status="AVAILABLE"),
    dict(id="CCT013", employee_id="EMP003", vendor="Air India",        amount=15000.0, currency="INR", transaction_date=date(2026, 7, 24), card_last_four="1111", status="AVAILABLE"),
    dict(id="CCT014", employee_id="EMP003", vendor="Uber",             amount=1200.0,  currency="INR", transaction_date=date(2026, 7, 25), card_last_four="1111", status="AVAILABLE"),
    dict(id="CCT015", employee_id="EMP003", vendor="Bukhara",          amount=2200.0,  currency="INR", transaction_date=date(2026, 7, 26), card_last_four="1111", status="AVAILABLE"),

    # --- EMP004 Bengaluru (TRIP005: 2026-08-01 to 2026-08-04) EXECUTIVE ---
    dict(id="CCT016", employee_id="EMP004", vendor="ITC Gardenia",     amount=19500.0, currency="INR", transaction_date=date(2026, 8, 1),  card_last_four="9999", status="AVAILABLE"),
    dict(id="CCT017", employee_id="EMP004", vendor="Vistara",          amount=9800.0,  currency="INR", transaction_date=date(2026, 7, 31), card_last_four="9999", status="AVAILABLE"),
    dict(id="CCT018", employee_id="EMP004", vendor="Ola",              amount=580.0,   currency="INR", transaction_date=date(2026, 8, 1),  card_last_four="9999", status="AVAILABLE"),
    dict(id="CCT019", employee_id="EMP004", vendor="Toit Brewpub",     amount=1800.0,  currency="INR", transaction_date=date(2026, 8, 2),  card_last_four="9999", status="AVAILABLE"),
]


# ------------------------------------------------------------------ #
# Seed runner                                                          #
# ------------------------------------------------------------------ #

def run_seed() -> None:
    """
    Entry point called from main.py lifespan on every startup.
    Exits immediately if seed data already exists (idempotent).
    """
    db: Session = SessionLocal()
    try:
        # Idempotency check — if policies already exist, skip everything.
        if db.query(TravelPolicy).count() > 0:
            return

        _seed_travel_policies(db)
        _seed_employees(db)
        _seed_trips(db)
        _seed_card_transactions(db)

        db.commit()
        print("[seed] Reference data seeded successfully.")

    except Exception as exc:
        db.rollback()
        raise RuntimeError(f"[seed] Seed failed: {exc}") from exc
    finally:
        db.close()


def _seed_travel_policies(db: Session) -> None:
    """Insert STANDARD and EXECUTIVE policies with their rules."""
    standard = TravelPolicy(
        name="STANDARD",
        description="Standard domestic travel policy for all employees",
    )
    executive = TravelPolicy(
        name="EXECUTIVE",
        description="Executive travel policy for senior staff and international travel",
    )
    db.add_all([standard, executive])
    db.flush()  # Ensure PKs exist before inserting FK-referencing rules

    for rule_data in _STANDARD_RULES:
        db.add(PolicyRule(policy_name="STANDARD", **rule_data))

    for rule_data in _EXECUTIVE_RULES:
        db.add(PolicyRule(policy_name="EXECUTIVE", **rule_data))


def _seed_employees(db: Session) -> None:
    """Insert all employees. Managers are referenced by ID — both must exist."""
    # Insert without manager FKs first to avoid FK violations on self-reference
    for emp_data in _EMPLOYEES:
        db.add(Employee(**{**emp_data, "manager_id": None}))
    db.flush()

    # Now set manager references
    for emp_data in _EMPLOYEES:
        if emp_data["manager_id"]:
            emp = db.get(Employee, emp_data["id"])
            if emp:
                emp.manager_id = emp_data["manager_id"]


def _seed_trips(db: Session) -> None:
    for trip_data in _TRIPS:
        db.add(Trip(**trip_data))


def _seed_card_transactions(db: Session) -> None:
    for txn_data in _CARD_TRANSACTIONS:
        db.add(CorporateCardTransaction(**txn_data))
