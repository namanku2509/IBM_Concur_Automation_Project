"""
repositories/employee_repo.py
------------------------------
Database access layer for the Employee domain.

All queries that touch the `employees` table are centralised here.
Services import and call these functions — no SQL outside this file.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.employee import Employee


def get_by_id(employee_id: str, db: Session) -> Employee | None:
    """Return the Employee with the given ID, or None if not found."""
    return db.get(Employee, employee_id)


def get_all(db: Session) -> list[Employee]:
    """Return all employees, ordered by name."""
    return db.query(Employee).order_by(Employee.name).all()


def get_active_by_id(employee_id: str, db: Session) -> Employee | None:
    """
    Return the Employee only if they exist AND are active.
    Returns None for both not-found and inactive cases — the caller
    (service layer) distinguishes using a subsequent get_by_id check.
    """
    return (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.is_active.is_(True))
        .first()
    )


def exists(employee_id: str, db: Session) -> bool:
    """Return True if an employee with this ID exists (active or inactive)."""
    return db.query(Employee.id).filter(Employee.id == employee_id).first() is not None
