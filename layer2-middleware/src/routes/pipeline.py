"""
Pipeline route — POST /pipeline/run

Primary and only external entry point for Layer 1 (watsonx Orchestrate).
Accepts a batch of PDF receipt files plus report context, runs the full
5-stage pipeline on each file in PARALLEL, and returns aggregated results.

Parallelism note:
  All receipts are processed concurrently via asyncio.gather().
  On a CPU-only VM this reduces total wall-clock time from (N × T) to
  roughly T (time of the slowest single receipt) because OCR and LLM
  calls are I/O-bound from asyncio's perspective.
  A semaphore limits concurrency to MAX_CONCURRENT_RECEIPTS to prevent
  OOM on low-RAM VMs.

Duplicate detection:
  Within-batch duplicates (same file uploaded twice in one request) are
  caught before any async work using a seen_hashes dict keyed on SHA-256.
  Cross-batch duplicates (file uploaded in a previous request) are caught
  by Layer 3 returning HTTP 409 on POST /receipts/register — the pipeline
  catches DuplicateReceiptError and returns status="duplicate".
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.models.pipeline_models import (
    AirfareDetailResult,
    HotelDetailResult,
    MealDetailResult,
    PipelineResult,
    PipelineSummary,
    ReceiptResult,
    RegistrationDetailResult,
    TaxiDetailResult,
)
from src.services.hash_service import compute_sha256

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pipeline"])

# Max receipts to process concurrently — prevents OOM on 4GB RAM VMs
# Docling loads a ~500MB model per worker; 3 concurrent = ~1.5GB
MAX_CONCURRENT_RECEIPTS = 3


@router.post(
    "/pipeline/run",
    response_model=PipelineResult,
    summary="Process all receipts for an expense report",
    description=(
        "Accepts multiple PDF receipt files for a single business trip. "
        "For each PDF the pipeline runs: "
        "(1) OCR via Docling (local, no API key), "
        "(2) expense categorisation via Ollama llama3.2:3b (local LLM), "
        "(3) intelligent field extraction grounded in the Layer 3 DB schema, "
        "(4) fuzzy matching against corporate card transactions from Layer 3, "
        "(5) payload translation and submission to Layer 3. "
        "All receipts are processed in parallel (up to 3 at a time); a failure "
        "on one file does not abort the batch. "
        "Set DRY_RUN=true in the environment to skip Layer 3 submission steps."
    ),
)
async def run_pipeline(
    files: Annotated[
        list[UploadFile],
        File(description="PDF receipt files — all receipts for one trip"),
    ],
    report_id: Annotated[
        str,
        Form(description="Expense report ID from Layer 3 (e.g. RPT001)"),
    ],
    employee_id: Annotated[
        str,
        Form(description="Employee ID from Layer 3 (e.g. EMP001)"),
    ],
    payment_hint: Annotated[
        str,
        Form(description="'card' (default) or 'cash'. Cash receipts skip card matching and are recorded as PERSONAL_CASH."),
    ] = "card",
) -> PipelineResult:
    if not files:
        raise HTTPException(status_code=422, detail="At least one PDF file is required.")

    for upload in files:
        if upload.content_type not in ("application/pdf", "application/octet-stream"):
            if not (upload.filename or "").lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=422,
                    detail=f"'{upload.filename}' does not appear to be a PDF.",
                )

    # Read all file bytes upfront (before async tasks, avoids stream exhaustion)
    file_payloads: list[tuple[str, bytes]] = []
    for upload in files:
        filename = upload.filename or "unknown.pdf"
        file_bytes = await upload.read()
        file_payloads.append((filename, file_bytes))

    logger.info(
        "Pipeline started | report=%s employee=%s files=%d (parallel, max %d)",
        report_id, employee_id, len(file_payloads), MAX_CONCURRENT_RECEIPTS,
    )

    # ── Within-batch duplicate detection ─────────────────────────────────────
    # Hash every file now (cheap, synchronous) so we can short-circuit duplicates
    # before spending Docling + Ollama time on them.
    # seen_hashes: hash → (filename, index) of the first occurrence in this batch
    seen_hashes: dict[str, tuple[str, int]] = {}
    deduplicated_payloads: list[tuple[str, bytes]] = []
    within_batch_duplicates: list[ReceiptResult] = []

    for idx, (filename, file_bytes) in enumerate(file_payloads):
        file_hash = compute_sha256(file_bytes)
        if file_hash in seen_hashes:
            original_filename, _ = seen_hashes[file_hash]
            logger.warning(
                "Within-batch duplicate | file=%s | identical to %s in this batch",
                filename, original_filename,
            )
            within_batch_duplicates.append(ReceiptResult(
                filename=filename,
                status="duplicate",
                file_hash=file_hash,
                error_message=(
                    f"This receipt is identical to '{original_filename}' "
                    "which was already submitted in this batch."
                ),
            ))
        else:
            seen_hashes[file_hash] = (filename, idx)
            deduplicated_payloads.append((filename, file_bytes))

    # Semaphore prevents more than MAX_CONCURRENT_RECEIPTS running at once
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_RECEIPTS)

    # Shared claim ledger: prevents two receipts from matching the same card txn
    from src.services.matching_service import _ClaimLedger
    from src.services.concur_client import fetch_available_transactions
    claim_ledger = _ClaimLedger()

    available_transactions = None
    if payment_hint != "cash":
        try:
            available_transactions = await fetch_available_transactions(employee_id, report_id)
        except Exception as exc:
            logger.warning(
                "Could not prefetch available transactions from Layer 3: %s — proceeding with no match.",
                exc,
            )
            available_transactions = []

    async def process_one(filename: str, file_bytes: bytes) -> ReceiptResult:
        async with semaphore:
            return await _process_single_receipt(
                filename, file_bytes, report_id, employee_id, claim_ledger,
                payment_hint=payment_hint,
                available_transactions=available_transactions,
            )

    # Run all unique receipts in parallel
    processed_results: list[ReceiptResult] = await asyncio.gather(
        *[process_one(fn, fb) for fn, fb in deduplicated_payloads],
        return_exceptions=False,
    )

    # Merge processed results + within-batch duplicates, preserving upload order
    results: list[ReceiptResult] = list(processed_results) + within_batch_duplicates

    # Aggregate
    total_amount = 0.0
    matched_count = 0
    by_type: dict[str, int] = {}

    for r in results:
        if r.status == "success":
            total_amount += r.amount or 0.0
            if r.matched_txn_id:
                matched_count += 1
            if r.expense_type:
                by_type[r.expense_type] = by_type.get(r.expense_type, 0) + 1

    unmatched   = sum(1 for r in results if r.status == "success" and not r.matched_txn_id)
    errors      = sum(1 for r in results if r.status == "error")
    duplicates  = sum(1 for r in results if r.status == "duplicate")

    return PipelineResult(
        report_id=report_id,
        employee_id=employee_id,
        processed=len(files),
        matched=matched_count,
        unmatched=unmatched,
        errors=errors,
        duplicates=duplicates,
        results=results,
        summary=PipelineSummary(
            total_amount=round(total_amount, 2),
            currency="INR",
            by_type=by_type,
        ),
    )


async def _process_single_receipt(
    filename: str,
    file_bytes: bytes,
    report_id: str,
    employee_id: str,
    claim_ledger=None,
    payment_hint: str = "card",
    available_transactions=None,
) -> ReceiptResult:
    """Process one receipt through all 5 pipeline stages. Never raises — errors are captured."""

    from src.services.ocr_service import extract_text
    from src.services.categorisation_service import categorise
    from src.services.extraction_service import extract
    from src.services.matching_service import match
    from src.services.schema_mapper import build_receipt_register_request
    from src.services.concur_client import register_receipt, DuplicateReceiptError
    from src import config

    logger.info("Processing receipt: %s", filename)

    try:
        # Stage 1 — OCR
        ocr_result = await extract_text(file_bytes, filename)

        # Guard: wrong drop zone — run BEFORE the empty-text bail-out so that
        # a card receipt uploaded to the cash box (or vice versa) always gets
        # the clear wrong-box message even when OCR text is sparse.
        raw_text_for_detection = ocr_result.raw_text or ""
        detected_mode = _detect_payment_mode(raw_text_for_detection)
        logger.info("Payment mode detected: %s | hint: %s | file: %s", detected_mode, payment_hint, filename)

        if payment_hint == "card" and detected_mode == "cash":
            return ReceiptResult(
                filename=filename,
                status="error",
                file_hash=ocr_result.file_hash,
                error_message=(
                    "This receipt shows a Cash payment. "
                    "Please upload it using the 'Cash / Out-of-Pocket Receipts' drop box."
                ),
            )

        if payment_hint == "cash" and detected_mode == "card":
            return ReceiptResult(
                filename=filename,
                status="error",
                file_hash=ocr_result.file_hash,
                error_message=(
                    "This receipt shows a Corporate Card payment. "
                    "Please upload it using the 'Corporate Card Receipts' drop box."
                ),
            )

        # Guard: empty OCR text means Docling could not read the PDF.
        # Checked after wrong-box detection so a misplaced receipt gets the
        # actionable wrong-box message rather than a generic "scanned image" error.
        if not raw_text_for_detection or len(raw_text_for_detection.strip()) < 20:
            logger.warning(
                "OCR produced no usable text for '%s' (%d chars) — "
                "receipt is likely a scanned image PDF with no text layer.",
                filename, len(raw_text_for_detection),
            )
            return ReceiptResult(
                filename=filename,
                status="error",
                file_hash=ocr_result.file_hash,
                error_message=(
                    "OCR could not extract text from this receipt. "
                    "The PDF may be a scanned image. "
                    "Try printing to PDF from the original application, or use a clearer scan."
                ),
            )

        # Stage 2 — Categorise
        cat_result = await categorise(ocr_result.raw_text)

        # Stage 3 — Extract
        extracted = await extract(ocr_result, cat_result)

        # Stage 4 — Match (skipped for cash receipts — no card transaction expected)
        if payment_hint == "cash":
            # Cash upload: bypass card matching entirely, mark as personal cash
            from src.services.matching_service import MatchResult
            match_result = MatchResult(txn_id=None, confidence=0.0, score_vendor=0.0, score_amount=0.0, score_date=0.0)
            extracted.payment_type = "OUT_OF_POCKET"
        else:
            match_result = await match(
                extracted,
                employee_id,
                report_id,
                claim_ledger,
                available_transactions=available_transactions,
            )
            if match_result.txn_id:
                extracted.payment_type = "CORPORATE_CARD"

        # Stage 5 — Register receipt (cross-batch duplicate check via Layer 3 409)
        receipt_id = None
        warnings: list = []

        dry_run = config.DRY_RUN

        if not dry_run:
            receipt_req = build_receipt_register_request(extracted, employee_id, filename)
            try:
                receipt_resp = await register_receipt(receipt_req)
                receipt_id = receipt_resp.receipt_id
            except DuplicateReceiptError as dup:
                # Receipt was already registered in a previous run — reuse the existing
                # receipt ID and continue building a full success result rather than
                # returning a dead-end duplicate with no expense data.
                logger.info(
                    "Cross-batch duplicate | file=%s | reusing existing_id=%s",
                    filename, dup.existing_receipt_id,
                )
                receipt_id = dup.existing_receipt_id or None

        exp_type = extracted.expense_type
        date_str = (
            extracted.transaction_date.isoformat()
            if extracted.transaction_date else None
        )

        # Build type-specific detail sub-objects
        hotel_detail_result = None
        airfare_detail_result = None
        taxi_detail_result = None
        meal_detail_result = None
        registration_detail_result = None

        if exp_type == "HOTEL" and extracted.hotel_detail:
            hd = extracted.hotel_detail
            hotel_detail_result = HotelDetailResult(
                check_in_date=hd.check_in_date.isoformat() if hd.check_in_date else None,
                check_out_date=hd.check_out_date.isoformat() if hd.check_out_date else None,
                num_nights=hd.num_nights,
                nightly_rate=hd.nightly_rate,
                tax_amount=hd.tax_amount,
            )
        elif exp_type == "FLIGHT" and extracted.airfare_detail:
            ad = extracted.airfare_detail
            airfare_detail_result = AirfareDetailResult(
                origin=ad.origin,
                destination=ad.destination,
                airline=ad.airline,
                ticket_number=ad.ticket_number,
                travel_class=ad.travel_class,
                passenger_name=ad.passenger_name,
            )
        elif exp_type == "TAXI" and extracted.taxi_detail:
            td = extracted.taxi_detail
            taxi_detail_result = TaxiDetailResult(
                from_location=td.from_location,
                to_location=td.to_location,
                distance_km=td.distance_km,
            )
        elif exp_type == "MEALS" and extracted.meal_detail:
            md = extracted.meal_detail
            meal_detail_result = MealDetailResult(
                meal_type=md.meal_type,
                num_attendees=md.num_attendees,
                business_justification=md.business_justification,
            )
        elif exp_type == "REGISTRATION" and extracted.registration_detail:
            rd = extracted.registration_detail
            registration_detail_result = RegistrationDetailResult(
                event_name=rd.event_name,
                event_date=rd.event_date.isoformat() if rd.event_date else None,
                registration_id=rd.registration_id,
                organiser=rd.organiser,
            )

        return ReceiptResult(
            filename=filename,
            status="success",
            expense_type=exp_type,
            vendor=extracted.vendor,
            amount=extracted.amount,
            currency=extracted.currency,
            transaction_date=date_str,
            city=extracted.city,
            payment_type=extracted.payment_type,
            hotel_detail=hotel_detail_result,
            airfare_detail=airfare_detail_result,
            taxi_detail=taxi_detail_result,
            meal_detail=meal_detail_result,
            registration_detail=registration_detail_result,
            matched_txn_id=match_result.txn_id,
            match_confidence=match_result.confidence,
            expense_id=receipt_id,
            warnings=warnings,
            ocr_engine=extracted.ocr_engine,
            page_count=ocr_result.page_count,
            file_hash=ocr_result.file_hash,
            dry_run=dry_run,
        )

    except Exception as exc:
        logger.error("Failed to process '%s': %s", filename, exc, exc_info=True)
        return ReceiptResult(
            filename=filename,
            status="error",
            error_message=str(exc),
        )

def _detect_payment_mode(text: str) -> str:
    """
    Detect whether a receipt is a cash or corporate-card payment from OCR text.

    Returns:
        "card"    — receipt explicitly shows corporate/credit/debit card payment
        "cash"    — receipt explicitly shows cash payment
        "unknown" — payment mode not determinable from text (let it through)
    """
    import re
    t = text.lower()

    # Card signals — ordered most specific first
    card_patterns = [
        r"corporate\s*card",
        r"card\s*xxxx",
        r"credit\s*card",
        r"debit\s*card",
        r"card\s*no\.?\s*\d",
        r"visa|mastercard|rupay|amex",
        r"payment\s*mode\s*[:\|]?\s*card",
        r"paid\s*by\s*card",
    ]
    for p in card_patterns:
        if re.search(p, t):
            return "card"

    # Cash signals
    cash_patterns = [
        r"payment\s*mode\s*[:\|]?\s*cash",
        r"payment\s*mode\s*cash",          # handles "Payment Mode Cash Amount Paid"
        r"paid\s*by\s*cash",
        r"amount\s*paid\s*[:\|]?\s*cash",
        r"cash\s*payment",
        r"payment\s*:\s*cash",
    ]
    for p in cash_patterns:
        if re.search(p, t):
            return "cash"

    return "unknown"

