"""
test_pipeline.py — End-to-end pipeline test script.

Calls POST /pipeline/run with all 6 sample receipt PDFs and pretty-prints
the results. Layer 2 server must be running before executing this script.

Usage:
    # Start Layer 2 server in one terminal:
    uvicorn main:app --reload --port 8000

    # Run this test in another terminal:
    python test_pipeline.py

    # To test without Layer 3 (DRY_RUN mode):
    DRY_RUN=true python test_pipeline.py

    # To test against a specific server:
    LAYER2_URL=http://localhost:8000 python test_pipeline.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8000")
SAMPLE_DIR = Path(__file__).parent / "data" / "sample_receipts"

REPORT_ID = "RPT001"
EMPLOYEE_ID = "EMP001"

# Expected sample PDF filenames
EXPECTED_FILES = [
    "hotel_marriott.pdf",
    "taxi_ola.pdf",
    "flight_indigo.pdf",
    "meals_restaurant.pdf",
    "meals_conference.pdf",
    "misc_pharmacy.pdf",
]


def main() -> None:
    print("=" * 60)
    print("Layer 2 — AI Middleware End-to-End Pipeline Test")
    print("=" * 60)
    print(f"Server  : {LAYER2_URL}")
    print(f"Report  : {REPORT_ID}")
    print(f"Employee: {EMPLOYEE_ID}")
    print()

    # ── Check server health ───────────────────────────────────────────────────
    print("1. Checking server health...")
    try:
        with urllib.request.urlopen(f"{LAYER2_URL}/health", timeout=5) as resp:
            health = json.loads(resp.read())
            print(f"   ✓ {health}")
    except Exception as exc:
        print(f"   ✗ Server not reachable: {exc}")
        print("   Make sure Layer 2 is running: uvicorn main:app --reload --port 8000")
        sys.exit(1)

    # ── Check AI engine status ────────────────────────────────────────────────
    print("\n2. Checking AI engine status...")
    try:
        with urllib.request.urlopen(f"{LAYER2_URL}/watsonx/status", timeout=10) as resp:
            status = json.loads(resp.read())
            print(f"   OCR engine   : {status.get('ocr_engine')} ({status.get('ocr_status')})")
            print(f"   LLM engine   : {status.get('llm_engine')} ({status.get('llm_status')})")
            print(f"   Ollama model : {status.get('ollama_model')}")
            print(f"   DRY_RUN      : {status.get('dry_run')}")
    except Exception as exc:
        print(f"   ✗ Could not check AI status: {exc}")

    # ── Locate PDF files ──────────────────────────────────────────────────────
    print(f"\n3. Looking for sample PDFs in: {SAMPLE_DIR}")
    available = list(SAMPLE_DIR.glob("*.pdf"))

    if not available:
        print(f"   ✗ No PDF files found in {SAMPLE_DIR}")
        print("   Generate sample PDFs: python data/generate_sample_pdfs.py")
        print("   Or place your own PDFs in data/sample_receipts/")
        sys.exit(1)

    print(f"   Found {len(available)} PDF(s):")
    for f in available:
        print(f"   • {f.name}")

    # ── Build multipart request ───────────────────────────────────────────────
    print(f"\n4. Sending {len(available)} PDF(s) to POST /pipeline/run ...")

    # Build multipart/form-data manually (no external deps)
    boundary = "----PipelineTestBoundary12345"
    body_parts = []

    for pdf_path in available:
        pdf_bytes = pdf_path.read_bytes()
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{pdf_path.name}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode() + pdf_bytes + b"\r\n"
        body_parts.append(part)

    # Add form fields
    for field, value in [("report_id", REPORT_ID), ("employee_id", EMPLOYEE_ID)]:
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()
        body_parts.append(part)

    body_parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(body_parts)

    req = urllib.request.Request(
        f"{LAYER2_URL}/pipeline/run",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode()
        print(f"   ✗ HTTP {exc.code}: {body_text[:500]}")
        sys.exit(1)
    except Exception as exc:
        print(f"   ✗ Request failed: {exc}")
        sys.exit(1)

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n5. Results")
    print("─" * 60)
    print(f"  Report ID  : {result.get('report_id')}")
    print(f"  Processed  : {result.get('processed')}")
    print(f"  Matched    : {result.get('matched')} (card transaction matched)")
    print(f"  Unmatched  : {result.get('unmatched')}")
    print(f"  Errors     : {result.get('errors', 0)}")
    print()

    summary = result.get("summary", {})
    print(f"  Total amount : {summary.get('currency')} {summary.get('total_amount')}")
    print(f"  By type      : {summary.get('by_type')}")
    print()

    print("  Per-receipt results:")
    print("  " + "─" * 56)
    for r in result.get("results", []):
        status_icon = "✓" if r.get("status") == "success" else "✗"
        print(f"  {status_icon} {r.get('filename')}")
        if r.get("status") == "success":
            print(f"      Type      : {r.get('expense_type')}")
            print(f"      Vendor    : {r.get('vendor')}")
            print(f"      Amount    : {r.get('currency')} {r.get('amount')}")
            print(f"      Date      : {r.get('transaction_date')}")
            print(f"      City      : {r.get('city')}")
            print(f"      Card match: {r.get('matched_txn_id')} (conf={r.get('match_confidence')})")
            print(f"      Expense ID: {r.get('expense_id')}")
            print(f"      OCR engine: {r.get('ocr_engine')}")
            if r.get("warnings"):
                print(f"      Warnings  : {r.get('warnings')}")
            if r.get("dry_run"):
                print(f"      [DRY RUN — Layer 3 submission skipped]")
        else:
            print(f"      Error: {r.get('error_message')}")
        print()

    print("─" * 60)
    errors = result.get("errors", 0)
    if errors == 0:
        print(f"✓ Pipeline completed successfully — {result.get('processed')} receipts processed")
    else:
        print(f"⚠ Pipeline completed with {errors} error(s)")


if __name__ == "__main__":
    main()
