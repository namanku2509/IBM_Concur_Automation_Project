"""
Concur client — HTTP client for all Layer 3 calls.

Aligned with concur-stub actual API (2026-01):
  POST /api/v4/receipts/register                        — register receipt metadata, get receiptId
  GET  /api/v4/card-transactions?employeeId=<id>        — available card transactions
  POST /api/v4/expense-reports/{report_id}/expenses     — bulk expense ingestion

All endpoint paths are read from config.LAYER3_ENDPOINTS.
Never hardcode a Layer 3 URL in this file or any other service.

DRY_RUN mode: when config.DRY_RUN is True, write calls are
skipped and mock responses are returned so the pipeline can be
fully tested (OCR + extraction + matching) without Layer 3 running.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from src import config
from src.models.concur_models import (
    AvailableTransaction,
    ReceiptRegisterRequest,
    ReceiptRegisterResponse,
    SubmitExpensesResponse,
)

logger = logging.getLogger(__name__)


class ConcurClientError(Exception):
    """Raised when Layer 3 returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Layer 3 error {status_code}: {detail}")


class DuplicateReceiptError(Exception):
    """
    Raised when Layer 3 returns HTTP 409 on POST /receipts/register.
    Carries the existing receipt_id so the pipeline can reuse it.
    """

    def __init__(self, existing_receipt_id: str, registered_at: str):
        self.existing_receipt_id = existing_receipt_id
        self.registered_at = registered_at
        super().__init__(f"Duplicate receipt — existing id: {existing_receipt_id}")


def _auth_headers() -> dict:
    """Return auth headers to include on every Layer 3 request."""
    headers = {}
    if config.LAYER3_API_KEY:
        headers["X-API-Key"] = config.LAYER3_API_KEY
    return headers


# ── Register receipt ──────────────────────────────────────────────────────────

async def register_receipt(
    payload: ReceiptRegisterRequest,
) -> ReceiptRegisterResponse:
    """
    POST /api/v4/receipts/register
    Registers receipt metadata with Layer 3 and returns a receiptId
    to include in the expense submission payload.

    DRY_RUN: returns a mock ReceiptRegisterResponse without calling Layer 3.
    """
    if config.DRY_RUN:
        logger.info("DRY_RUN | register_receipt skipped | hash=%s", payload.receipt_hash)
        return ReceiptRegisterResponse(
            receipt_id=f"DRY-RCP-{payload.receipt_hash[:8]}",
            employee_id=payload.employee_id,
            registered_at="",
        )

    url = config.layer3_url("register_receipt")
    logger.info("POST %s | employee_id=%s", url, payload.employee_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json=payload.model_dump(mode="json", by_alias=True),
            headers=_auth_headers(),
        )

    # 409 = duplicate receipt — raise a typed error so the pipeline can handle it
    # FastAPI wraps HTTPException bodies inside a "detail" key, so the actual
    # DuplicateReceiptResponse fields are at data["detail"], not data directly.
    if resp.status_code == 409:
        data = resp.json()
        body = data.get("detail", data)   # unwrap FastAPI envelope if present
        if isinstance(body, str):
            body = data                   # plain string detail — fall back to root
        raise DuplicateReceiptError(
            existing_receipt_id=body.get("existingReceiptId", ""),
            registered_at=body.get("registeredAt", ""),
        )

    _raise_for_status(resp)
    data = resp.json()
    return ReceiptRegisterResponse(
        receipt_id=data.get("receiptId", data.get("receipt_id", "")),
        employee_id=data.get("employeeId", data.get("employee_id", payload.employee_id)),
        registered_at=data.get("registeredAt", data.get("registered_at", "")),
    )


# ── Fetch available transactions ──────────────────────────────────────────────

async def fetch_available_transactions(
    employee_id: str,
    report_id: Optional[str] = None,
) -> list[AvailableTransaction]:
    """
    GET /api/v4/card-transactions?employeeId=<id>
    Returns corporate card transactions for the employee.

    DRY_RUN: returns an empty list.
    """
    if config.DRY_RUN:
        logger.info("DRY_RUN | fetch_available_transactions returning empty list")
        return []

    url = config.layer3_url("available_transactions")
    logger.info("GET %s | employee_id=%s", url, employee_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            url,
            params={"employeeId": employee_id},
            headers=_auth_headers(),
        )

    _raise_for_status(resp)
    data = resp.json()

    # Layer 3 returns { employeeId, transactions[], total }
    if isinstance(data, list):
        items = data
    else:
        items = data.get("transactions", data.get("data", []))

    result = []
    for item in items:
        # Normalise camelCase → snake_case for AvailableTransaction model
        result.append(AvailableTransaction(
            txn_id=item.get("transactionId", item.get("txn_id", "")),
            employee_id=item.get("employeeId", item.get("employee_id", employee_id)),
            vendor=item.get("vendor"),
            amount=item.get("amount", 0.0),
            currency=item.get("currency", "INR"),
            transaction_date=item.get("transactionDate", item.get("transaction_date")),
            status=item.get("status", "AVAILABLE"),
            matched_expense_id=item.get("matchedExpenseId", item.get("matched_expense_id")),
        ))
    return result


# ── Shared error handler ──────────────────────────────────────────────────────

def _raise_for_status(resp: httpx.Response) -> None:
    """Raise ConcurClientError for non-2xx responses with Layer 3's error body."""
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise ConcurClientError(resp.status_code, str(detail))
