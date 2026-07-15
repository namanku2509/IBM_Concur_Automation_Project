"""
Health & watsonx status routes.

GET /health        — liveness probe
GET /watsonx/status — reports whether Docling and Ollama are ready
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src import config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    return {"status": "ok", "service": "layer2-ai-middleware"}


@router.get(
    "/watsonx/status",
    summary="AI engine status",
    description="Reports whether Docling (OCR) and Ollama (LLM) are ready.",
)
async def watsonx_status() -> dict:
    # Check Ollama
    ollama_ok = config.ollama_configured()
    ollama_model = config.OLLAMA_MODEL

    # Check Docling (just import check — no network)
    try:
        from docling.document_converter import DocumentConverter  # noqa: F401
        docling_ok = True
    except ImportError:
        docling_ok = False

    return {
        "ocr_engine":    "docling",
        "ocr_status":    "ready" if docling_ok else "not-installed",
        "llm_engine":    "ollama",
        "llm_status":    "connected" if ollama_ok else "not-running",
        "ollama_model":  ollama_model,
        "ollama_host":   config.OLLAMA_HOST,
        "dry_run":       config.DRY_RUN,
        "layer3_url":    config.LAYER3_BASE_URL,
        "note": (
            "No API keys needed. OCR runs via Docling locally. "
            "LLM runs via Ollama locally on Apple Silicon."
        ),
    }
