"""
Layer 2 — AI Middleware
Configuration: environment variables + Layer 3 endpoint path table.

NO API KEYS NEEDED.
OCR   → Docling (IBM open-source, runs locally)
LLM   → Ollama  (local LLM server, runs on Apple Silicon via Metal)

To point Layer 2 at Layer 3's final API, update LAYER3_ENDPOINTS below.
No other file needs to change.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


# ── Local AI (Ollama) ────────────────────────────────────────────────────────

# Ollama server — started with `ollama serve` in a terminal
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Model for categorisation + extraction
# llama3.2:3b runs fast on Apple Silicon M-series (< 2GB RAM)
# Override via env var if you have a different model pulled
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Generation params — deterministic output for structured extraction
OLLAMA_PARAMS: dict = {
    "temperature": 0,
    "num_predict": 512,
}


# ── Layer 3 ─────────────────────────────────────────────────────────────────

LAYER3_BASE_URL: str = os.getenv("LAYER3_BASE_URL", "http://localhost:8001")

# API key sent as X-API-Key header on every Layer 3 request.
# In local dev, Layer 3 (concur-stub) does not enforce auth, but we keep
# the header so the pattern is in place for real Concur integration.
LAYER3_API_KEY: str = os.getenv("LAYER3_API_KEY", "")

# All Layer 3 endpoint paths live here ONLY.
# Aligned with concur-stub actual routers (as of 2026-01):
#   POST   /api/v4/receipts/register                          — register receipt, get receiptId
#   GET    /api/v4/card-transactions?employeeId=<id>          — available card transactions
#   POST   /api/v4/expense-reports/{report_id}/expenses       — bulk expense ingestion
LAYER3_ENDPOINTS: dict[str, str] = {
    # POST   — register receipt metadata, receive receiptId
    "register_receipt": "/api/v4/receipts/register",
    # GET    — list corporate card transactions for an employee
    "available_transactions": "/api/v4/card-transactions",
    # POST   — bulk submit all expenses for a report
    "submit_expenses": "/api/v4/expense-reports/{report_id}/expenses",
}


def layer3_url(endpoint_key: str, **path_params: str) -> str:
    """Build a full Layer 3 URL from an endpoint key and path parameters."""
    path_template = LAYER3_ENDPOINTS[endpoint_key]
    path = path_template.format(**path_params)
    return f"{LAYER3_BASE_URL}{path}"


# ── Runtime flags ───────────────────────────────────────────────────────────

# When True, Layer 3 submit/attach/link calls are skipped.
DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").upper()


# ── Capability check ─────────────────────────────────────────────────────────

def ollama_configured() -> bool:
    """Return True if Ollama server is reachable."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False
