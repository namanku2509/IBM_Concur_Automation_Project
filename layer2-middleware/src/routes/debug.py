"""
Debug route — POST /pipeline/debug

Runs a single PDF through OCR + categorisation + extraction only
(no matching, no Layer 3 calls) and returns the raw intermediate
results so you can diagnose what Docling and Ollama actually see.

This endpoint is intentionally NOT included in /openapi.json
for Orchestrate — it is a dev-only diagnostic tool.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Debug"])


class DebugResult(BaseModel):
    filename: str
    file_hash: str
    ocr_chars: int
    ocr_pages: int
    ocr_text_preview: str          # first 2000 chars
    ocr_text_full: str             # full text
    category: str
    category_confidence: float
    category_reasoning: str | None
    extracted_vendor: str | None
    extracted_amount: float
    extracted_currency: str | None
    extracted_date: str | None
    extracted_city: str | None
    extracted_expense_type: str


@router.post(
    "/pipeline/debug",
    response_model=DebugResult,
    summary="Debug single receipt — OCR + categorise + extract only",
    description=(
        "Upload one PDF to see exactly what Docling extracts and what the LLM "
        "infers from it. No matching or Layer 3 calls are made. "
        "Use this to diagnose zero-amount / unmatched receipts."
    ),
)
async def debug_receipt(
    file: Annotated[UploadFile, File(description="Single PDF receipt to debug")],
) -> DebugResult:
    from src.services.ocr_service import extract_text
    from src.services.categorisation_service import categorise
    from src.services.extraction_service import extract

    filename = file.filename or "unknown.pdf"
    file_bytes = await file.read()

    # Stage 1 — OCR
    ocr_result = await extract_text(file_bytes, filename)

    if not ocr_result.raw_text or len(ocr_result.raw_text.strip()) < 20:
        return DebugResult(
            filename=filename,
            file_hash=ocr_result.file_hash,
            ocr_chars=len(ocr_result.raw_text),
            ocr_pages=ocr_result.page_count,
            ocr_text_preview="(empty — Docling could not extract text from this PDF)",
            ocr_text_full=ocr_result.raw_text,
            category="UNKNOWN",
            category_confidence=0.0,
            category_reasoning="OCR produced no usable text — PDF may be a scanned image with no text layer.",
            extracted_vendor=None,
            extracted_amount=0.0,
            extracted_currency=None,
            extracted_date=None,
            extracted_city=None,
            extracted_expense_type="UNKNOWN",
        )

    # Stage 2 — Categorise
    cat_result = await categorise(ocr_result.raw_text)

    # Stage 3 — Extract
    extracted = await extract(ocr_result, cat_result)

    date_str = (
        extracted.transaction_date.isoformat()
        if extracted.transaction_date else None
    )

    return DebugResult(
        filename=filename,
        file_hash=ocr_result.file_hash,
        ocr_chars=len(ocr_result.raw_text),
        ocr_pages=ocr_result.page_count,
        ocr_text_preview=ocr_result.raw_text[:2000],
        ocr_text_full=ocr_result.raw_text,
        category=cat_result.expense_type,
        category_confidence=cat_result.confidence,
        category_reasoning=cat_result.reasoning,
        extracted_vendor=extracted.vendor,
        extracted_amount=extracted.amount,
        extracted_currency=extracted.currency,
        extracted_date=date_str,
        extracted_city=extracted.city,
        extracted_expense_type=extracted.expense_type,
    )
