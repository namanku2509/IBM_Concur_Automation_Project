"""
routers/receipts.py
--------------------
POST /api/v4/receipts/register  — Register receipt metadata, get receiptId
GET  /api/v4/receipts/{id}      — Retrieve registered receipt metadata

The stub NEVER receives raw receipt images or binary data.
Layer 2 (AI Middleware) retains all binary assets after OCR processing.
Only structured metadata (hash, filename, MIME type, OCR confidence) is accepted.

Duplicate detection:
  If a receipt with the same SHA-256 hash is already registered for this
  employee, the endpoint returns HTTP 409 Conflict with the existing
  receiptId so Layer 2 can reuse it without re-processing.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.receipt import Receipt
from repositories import employee_repo, receipt_repo
from schemas.common import ErrorCode, ErrorResponse
from schemas.receipt import (
    DuplicateReceiptResponse,
    ReceiptRegisterRequest,
    ReceiptRegisterResponse,
    ReceiptResponse,
)

router = APIRouter(tags=["receipts"])


@router.post(
    "/receipts/register",
    response_model=ReceiptRegisterResponse,
    status_code=201,
    summary="Register receipt metadata",
    description=(
        "Called by Layer 2 after OCR processing. "
        "Accepts only structured metadata — no binary data is accepted. "
        "Returns a receiptId to include in the expense submission payload. "
        "Returns HTTP 409 if the same receipt (by SHA-256 hash) has already "
        "been registered for this employee — Layer 2 should reuse the "
        "existingReceiptId from the 409 body."
    ),
    responses={
        409: {"model": DuplicateReceiptResponse, "description": "Receipt already registered"},
    },
)
def register_receipt(
    payload: ReceiptRegisterRequest,
    db: Session = Depends(get_db),
) -> ReceiptRegisterResponse:
    # Validate employee
    if not employee_repo.get_by_id(payload.employee_id, db):
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.EMPLOYEE_NOT_FOUND,
                message=f"Employee {payload.employee_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )

    # ── Duplicate detection ───────────────────────────────────────────────────
    existing = receipt_repo.find_by_hash(payload.receipt_hash, payload.employee_id, db)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=DuplicateReceiptResponse(
                existingReceiptId=existing.id,
                employeeId=existing.employee_id,
                registeredAt=existing.registered_at,
            ).model_dump(by_alias=True, mode="json"),
        )

    receipt = Receipt(
        id=f"RCP-{uuid.uuid4().hex[:12].upper()}",
        employee_id=payload.employee_id,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        receipt_hash=payload.receipt_hash,
        ocr_confidence=payload.ocr_confidence,
    )
    receipt_repo.create(receipt, db)
    db.commit()

    return ReceiptRegisterResponse(
        receipt_id=receipt.id,
        employee_id=receipt.employee_id,
        registered_at=receipt.registered_at,
    )


@router.get(
    "/receipts/{receipt_id}",
    response_model=ReceiptResponse,
    summary="Get receipt metadata by ID",
    responses={404: {"model": ErrorResponse}},
)
def get_receipt(
    receipt_id: str,
    db: Session = Depends(get_db),
) -> ReceiptResponse:
    receipt = receipt_repo.get_by_id(receipt_id, db)
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                code=ErrorCode.REPORT_NOT_FOUND,
                message=f"Receipt {receipt_id!r} does not exist.",
            ).model_dump(by_alias=True),
        )
    return ReceiptResponse(
        receipt_id=receipt.id,
        employee_id=receipt.employee_id,
        registered_at=receipt.registered_at,
        file_name=receipt.file_name,
        mime_type=receipt.mime_type,
        ocr_confidence=receipt.ocr_confidence,
        receipt_hash=receipt.receipt_hash,
    )
