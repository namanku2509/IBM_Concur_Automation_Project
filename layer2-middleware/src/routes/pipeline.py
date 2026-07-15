"""
Pipeline route — POST /pipeline/run

Primary and only external entry point for Layer 1 (watsonx Orchestrate).
Accepts a batch of PDF receipt files plus report context, runs the full
5-stage pipeline on each file, and returns aggregated results.

Registered as a watsonx Orchestrate skill via /openapi.json.
"""

from __future__ import annotations

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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pipeline"])


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
        "All receipts are processed individually; a failure on one file does not "
        "abort the batch — the error is recorded in results and processing continues. "
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
) -> PipelineResult:
    """
    Full batch receipt pipeline.

    Each file is processed through:
      Stage 1: OCR   (ocr_service)
      Stage 2: Categorise  (categorisation_service)
      Stage 3: Extract     (extraction_service)
      Stage 4: Match       (matching_service)
      Stage 5: Submit      (schema_mapper + concur_client)
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one PDF file is required.")

    # Validate all uploads are PDFs
    for upload in files:
        if upload.content_type not in ("application/pdf", "application/octet-stream"):
            if not (upload.filename or "").lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=422,
                    detail=f"'{upload.filename}' does not appear to be a PDF. "
                           "Only PDF receipts are accepted.",
                )

    # ── Import services here to avoid circular imports at module load ─────────
    from src.services.ocr_service import extract_text
    from src.services.categorisation_service import categorise
    from src.services.extraction_service import extract
    from src.services.matching_service import match
    from src.services.schema_mapper import build_expense_input, build_receipt_register_request
    from src.services.concur_client import register_receipt, fetch_available_transactions
    from src import config

    results: list[ReceiptResult] = []
    total_amount = 0.0
    matched_count = 0
    by_type: dict[str, int] = {}

    for upload in files:
        filename = upload.filename or "unknown.pdf"
        logger.info("Processing receipt: %s", filename)

        try:
            file_bytes = await upload.read()

            # ── Stage 1 — OCR ─────────────────────────────────────────────
            ocr_result = await extract_text(file_bytes, filename)

            # ── Stage 2 — Categorise ──────────────────────────────────────
            cat_result = await categorise(ocr_result.raw_text)

            # ── Stage 3 — Extract ─────────────────────────────────────────
            extracted = await extract(ocr_result, cat_result)

            # ── Stage 4 — Match ───────────────────────────────────────────
            match_result = await match(extracted, employee_id, report_id)

            # Update payment_type based on match outcome
            if match_result.txn_id:
                extracted.payment_type = "CORPORATE_CARD"
                matched_count += 1

            # ── Stage 5 — Register receipt with Layer 3 ───────────────────
            receipt_id = None
            warnings: list = []
            dry_run = config.DRY_RUN

            if not dry_run:
                receipt_req = build_receipt_register_request(
                    extracted, employee_id, filename
                )
                receipt_resp = await register_receipt(receipt_req)
                receipt_id = receipt_resp.receipt_id

            # ── Aggregate ─────────────────────────────────────────────────
            total_amount += extracted.amount
            exp_type = extracted.expense_type
            by_type[exp_type] = by_type.get(exp_type, 0) + 1

            date_str = (
                extracted.transaction_date.isoformat()
                if extracted.transaction_date else None
            )

            # ── Build type-specific detail sub-object for the response ────────
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

            results.append(ReceiptResult(
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
            ))

        except Exception as exc:
            logger.error("Failed to process '%s': %s", filename, exc, exc_info=True)
            results.append(ReceiptResult(
                filename=filename,
                status="error",
                error_message=str(exc),
            ))

    unmatched = sum(1 for r in results if r.status == "success" and not r.matched_txn_id)
    errors = sum(1 for r in results if r.status == "error")

    return PipelineResult(
        report_id=report_id,
        employee_id=employee_id,
        processed=len(files),
        matched=matched_count,
        unmatched=unmatched,
        errors=errors,
        results=results,
        summary=PipelineSummary(
            total_amount=round(total_amount, 2),
            currency="INR",
            by_type=by_type,
        ),
    )
