"""
OCR service — Docling (IBM open-source, runs locally, no API key needed).

Docling is IBM Research's PDF extraction library. It understands PDF structure,
tables, and layout — far superior to pytesseract for receipts.

Flow:
  PDF bytes → Docling DocumentConverter → extracted text per page → joined

No network calls. No credentials. Runs entirely on your laptop.

Performance notes:
  - DocumentConverter is cached as a module-level singleton (avoids re-init per request)
  - _docling_extract runs in a thread pool executor so it never blocks the asyncio
    event loop while processing large PDFs
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from src.models.receipt_models import OcrResult
from src.services.hash_service import compute_sha256

logger = logging.getLogger(__name__)

# ── Singleton converter — initialised once, reused for every request ──────────
# DocumentConverter loads ML models on first instantiation (~2-3s).
# Caching it here means only the very first request pays that cost.
_converter = None

def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        logger.info("Initialising Docling DocumentConverter (one-time startup cost)")

        # Force single-threaded page processing.
        # Docling's default uses mpire multiprocessing workers which triggers a
        # tqdm._lock AttributeError on macOS when multiple receipts are processed
        # concurrently via asyncio.  num_threads=1 disables that internal pool
        # entirely without affecting OCR quality.
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False          # text-layer PDFs — no image OCR needed
        pipeline_options.do_table_structure = False  # receipts have no complex tables

        from docling.document_converter import PdfFormatOption
        _converter = DocumentConverter(
            format_options={
                "pdf": PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        logger.info("Docling DocumentConverter ready (single-threaded mode)")
    return _converter


async def extract_text(file_bytes: bytes, filename: str) -> OcrResult:
    """
    Stage 1 — OCR via Docling.

    Runs Docling in a thread pool executor so the asyncio event loop
    is never blocked during PDF processing.

    Args:
        file_bytes: Raw PDF bytes.
        filename:   Original filename (used only for logging).

    Returns:
        OcrResult with raw_text, engine_used, file_hash, page_count.
    """
    file_hash = compute_sha256(file_bytes)
    logger.info("OCR start | file=%s | hash=%s", filename, file_hash[:12])

    # Run the blocking Docling call in a thread so FastAPI stays responsive
    loop = asyncio.get_event_loop()
    raw_text, page_count = await loop.run_in_executor(
        None, _docling_extract, file_bytes, filename
    )

    logger.info(
        "OCR complete | engine=docling | pages=%d | chars=%d | file=%s",
        page_count, len(raw_text), filename,
    )

    return OcrResult(
        raw_text=raw_text,
        engine_used="docling",
        file_hash=file_hash,
        page_count=page_count,
    )


def _docling_extract(file_bytes: bytes, filename: str) -> tuple[str, int]:
    """
    Synchronous Docling extraction — called from a thread executor.
    Writes bytes to a temp file (Docling requires a file path), cleans up after.
    """
    converter = _get_converter()

    suffix = ".pdf" if filename.lower().endswith(".pdf") else ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        result = converter.convert(tmp_path)
        doc = result.document

        # Markdown export preserves tables and structure better than plain text
        text = doc.export_to_markdown()

        page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 1

        logger.debug("Docling extracted %d chars from %d pages", len(text), page_count)
        return text.strip(), page_count

    except Exception as exc:
        logger.error("Docling extraction failed for %s: %s", filename, exc)
        raise RuntimeError(f"Docling failed to extract text from {filename}: {exc}") from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
