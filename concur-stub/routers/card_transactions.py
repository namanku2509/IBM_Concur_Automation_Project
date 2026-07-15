"""
routers/card_transactions.py
------------------------------
GET  /api/v4/card-transactions?employeeId=EMP001   — Fetch card transactions
POST /admin/card-transactions                      — Inject transactions (test harness)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.corporate_card_transaction import CorporateCardTransaction
from repositories import card_transaction_repo, employee_repo
from schemas.card_transaction import (
    CardTransactionCreate,
    CardTransactionListResponse,
    CardTransactionResponse,
)
from schemas.common import CardTxnStatus, ErrorCode, ErrorResponse

router = APIRouter(tags=["card-transactions"])


@router.get(
    "/card-transactions",
    response_model=CardTransactionListResponse,
    summary="Get available corporate card transactions for an employee",
    description=(
        "Returns all corporate card transactions for the specified employee. "
        "Used by Layer 2 to display available expenses before matching."
    ),
)
def get_card_transactions(
    employee_id: str = Query(..., alias="employeeId", description="Employee ID to filter by"),
    status: Optional[str] = Query(default=None, description="Filter by status: AVAILABLE, MATCHED, IGNORED"),
    db: Session = Depends(get_db),
) -> CardTransactionListResponse:
    if not employee_repo.get_by_id(employee_id, db):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )

    if status:
        txns = card_transaction_repo.get_all_for_employee(employee_id, db)
        txns = [t for t in txns if t.status == status.upper()]
    else:
        txns = card_transaction_repo.get_all_for_employee(employee_id, db)

    return CardTransactionListResponse(
        employee_id=employee_id,
        transactions=[
            CardTransactionResponse(
                transaction_id=t.id,
                employee_id=t.employee_id,
                vendor=t.vendor,
                amount=t.amount,
                currency=t.currency,
                transaction_date=t.transaction_date,
                card_last_four=t.card_last_four,
                status=CardTxnStatus(t.status),
                matched_expense_id=t.matched_expense_id,
                created_at=t.created_at,
            )
            for t in txns
        ],
        total=len(txns),
    )


@router.post(
    "/admin/card-transactions",
    response_model=CardTransactionResponse,
    status_code=201,
    tags=["admin"],
    summary="[Admin] Inject a corporate card transaction",
    description=(
        "Test harness endpoint. Injects a card transaction without modifying seed data. "
        "Used during smoke testing and interactive demos."
    ),
)
def inject_card_transaction(
    payload: CardTransactionCreate,
    db: Session = Depends(get_db),
) -> CardTransactionResponse:
    if not employee_repo.get_by_id(payload.employee_id, db):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {payload.employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )

    txn = CorporateCardTransaction(
        id=payload.transaction_id,
        employee_id=payload.employee_id,
        vendor=payload.vendor,
        amount=payload.amount,
        currency=payload.currency.upper(),
        transaction_date=payload.transaction_date,
        card_last_four=payload.card_last_four,
        status="AVAILABLE",
    )
    card_transaction_repo.create(txn, db)
    db.commit()

    return CardTransactionResponse(
        transaction_id=txn.id,
        employee_id=txn.employee_id,
        vendor=txn.vendor,
        amount=txn.amount,
        currency=txn.currency,
        transaction_date=txn.transaction_date,
        card_last_four=txn.card_last_four,
        status=CardTxnStatus.AVAILABLE,
        matched_expense_id=None,
        created_at=txn.created_at,
    )
