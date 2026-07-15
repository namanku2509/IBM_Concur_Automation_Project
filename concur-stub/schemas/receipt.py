"""
schemas/receipt.py
------------------
Pydantic v2 schemas for the Receipt domain.

Design note:
    The stub never handles raw receipt images or PDFs.
    Layer 2 (AI Middleware) retains all binary assets.

    POST /api/v4/receipts/register  → ReceiptRegisterRequest → ReceiptRegisterResponse
    GET  /api/v4/receipts/{id}      →                          ReceiptResponse

Layer 2 calls /register after OCR processing to obtain a receiptId,
which is then included in the ExpenseInput payload when submitting expenses.
The receipt_hash is used for duplicate detection in Step 6 of the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReceiptRegisterRequest(BaseModel):
    """
    Request body for POST /api/v4/receipts/register.
    Layer 2 submits this after completing OCR on a receipt image.
    No binary data is accepted — metadata only.
    """
    model_config = ConfigDict(populate_by_name=True)

    employee_id: str = Field(
        ...,
        alias="employeeId",
        description="Employee who owns this receipt",
        examples=["EMP001"],
    )
    receipt_hash: str = Field(
        ...,
        alias="receiptHash",
        description=(
            "SHA-256 of vendor.lower() + ':' + str(amount) + ':' "
            "+ transactionDate + ':' + employee_id. "
            "Computed by Layer 2 and used for duplicate detection."
        ),
        examples=["a3f5e2..."],
    )
    file_name: Optional[str] = Field(
        default=None,
        alias="fileName",
        description="Original filename of the receipt, for display purposes",
        examples=["marriott_receipt_2026-07-21.pdf"],
    )
    mime_type: Optional[str] = Field(
        default=None,
        alias="mimeType",
        description="MIME type of the original file",
        examples=["application/pdf"],
    )
    ocr_confidence: Optional[float] = Field(
        default=None,
        alias="ocrConfidence",
        description="OCR confidence score (0.0–1.0) from Layer 2",
        ge=0.0,
        le=1.0,
        examples=[0.92],
    )


class ReceiptRegisterResponse(BaseModel):
    """Response returned after a receipt is registered."""
    model_config = ConfigDict(populate_by_name=True)

    receipt_id: str = Field(
        ...,
        alias="receiptId",
        description="Generated receipt ID to include in ExpenseInput.receiptId",
        examples=["RCP001"],
    )
    employee_id: str = Field(..., alias="employeeId")
    registered_at: datetime = Field(..., alias="registeredAt")


class ReceiptResponse(ReceiptRegisterResponse):
    """Full receipt metadata returned by GET /api/v4/receipts/{id}."""
    file_name: Optional[str] = Field(default=None, alias="fileName")
    mime_type: Optional[str] = Field(default=None, alias="mimeType")
    ocr_confidence: Optional[float] = Field(default=None, alias="ocrConfidence")
    receipt_hash: str = Field(..., alias="receiptHash")
