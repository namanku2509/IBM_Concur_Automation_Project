"""
Layer 2 — AI Middleware
FastAPI entry point.

Start the server:
    uvicorn main:app --reload --port 8000

The /openapi.json endpoint is used by watsonx Orchestrate to import
the pipeline as a registered skill. Ensure the server is reachable
from your Orchestrate tenant when importing.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import health, pipeline, debug

# ── Logging ──────────────────────────────────────────────────────────────────
log_level = os.getenv("LOG_LEVEL", "info").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Expense Claims AI Middleware",
    description=(
        "Layer 2 of the IBM Expense Claims Copilot. "
        "Receives PDF receipts from watsonx Orchestrate (Layer 1), "
        "extracts and categorises expenses using Docling (local OCR) and Ollama llama3.2:3b (local LLM — no API keys needed), "
        "matches them to corporate card transactions from the SAP Concur Stub (Layer 3), "
        "and submits structured expense payloads to Layer 3. "
        "\n\n"
        "Import /openapi.json into watsonx Orchestrate to register pipeline/run as a skill."
    ),
    version="1.0.0",
    # openapi_url default is /openapi.json — used by Orchestrate skill import
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow requests from watsonx Orchestrate and any local frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(pipeline.router)
app.include_router(debug.router)


# ── Startup log ───────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    from src.config import LAYER3_BASE_URL, DRY_RUN, ollama_configured, OLLAMA_MODEL, OLLAMA_HOST
    logger.info("─" * 60)
    logger.info("Layer 2 — AI Middleware started")
    logger.info("OCR engine    : Docling (local — no API key)")
    logger.info("LLM engine    : Ollama  (local — no API key)")
    logger.info("Ollama host   : %s", OLLAMA_HOST)
    logger.info("Ollama model  : %s", OLLAMA_MODEL)
    logger.info("Ollama status : %s", "RUNNING" if ollama_configured() else "NOT RUNNING — keyword fallback active")
    logger.info("Layer 3 URL   : %s", LAYER3_BASE_URL)
    logger.info("DRY_RUN       : %s", DRY_RUN)
    logger.info("OpenAPI spec  : http://localhost:8000/openapi.json")
    logger.info("─" * 60)
