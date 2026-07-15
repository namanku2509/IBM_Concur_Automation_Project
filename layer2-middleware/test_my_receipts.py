"""
test_my_receipts.py

Drop your real receipt PDFs into data/my_receipts/ and run this script.
It sends ALL of them together to the pipeline and prints the full JSON result.

Usage:
    python test_my_receipts.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

LAYER2_URL = "http://localhost:8000"
RECEIPTS_DIR = Path(__file__).parent / "data" / "my_receipts"
REPORT_ID    = "RPT001"
EMPLOYEE_ID  = "EMP001"


def main():
    # ── Create the folder if it doesn't exist ────────────────────────────────
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Real Receipt Test — Layer 2 AI Middleware")
    print("=" * 60)
    print(f"  Drop folder : {RECEIPTS_DIR}")
    print()

    # ── Find all PDFs in the folder ───────────────────────────────────────────
    pdfs = sorted(RECEIPTS_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"  No PDFs found in: {RECEIPTS_DIR}")
        print()
        print("  Steps:")
        print(f"  1. Open Finder:  open {RECEIPTS_DIR}")
        print("  2. Drop your PDF receipts into that folder")
        print("  3. Run this script again")
        sys.exit(0)

    print(f"  Found {len(pdfs)} PDF(s):")
    for p in pdfs:
        size_kb = p.stat().st_size // 1024
        print(f"    • {p.name}  ({size_kb} KB)")
    print()

    # ── Check server is alive ─────────────────────────────────────────────────
    print("  Checking server...")
    try:
        with urllib.request.urlopen(f"{LAYER2_URL}/health", timeout=5) as r:
            health = json.loads(r.read())
            print(f"  Server : {health.get('status', '?').upper()}")
    except Exception as exc:
        print(f"  Server not reachable: {exc}")
        print("  Make sure uvicorn is running on port 8000.")
        sys.exit(1)

    print(f"  Sending {len(pdfs)} file(s) to AI pipeline...")
    print("  (This takes 20-60 seconds per receipt — please wait)")
    print()

    # ── Build multipart/form-data request with ALL files ─────────────────────
    boundary = "----RealReceiptBoundary99887766"
    parts = []

    for pdf_path in pdfs:
        pdf_bytes = pdf_path.read_bytes()
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="files"; filename="{pdf_path.name}"\r\n'
                f"Content-Type: application/pdf\r\n\r\n"
            ).encode() + pdf_bytes + b"\r\n"
        )

    for field, value in [("report_id", REPORT_ID), ("employee_id", EMPLOYEE_ID)]:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )

    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"{LAYER2_URL}/pipeline/run",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            result = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code}: {exc.read().decode()[:500]}")
        sys.exit(1)
    except Exception as exc:
        print(f"  Request failed: {exc}")
        sys.exit(1)

    # ── Pretty-print full JSON ────────────────────────────────────────────────
    print("=" * 60)
    print("  FULL JSON RESPONSE")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    # ── Human-readable summary ────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Processed : {result.get('processed')}")
    print(f"  Errors    : {result.get('errors', 0)}")
    print(f"  Total     : {result['summary']['currency']} {result['summary']['total_amount']}")
    print()

    for r in result.get("results", []):
        icon = "✓" if r["status"] == "success" else "✗"
        print(f"  {icon}  {r['filename']}")
        if r["status"] == "success":
            print(f"       Category  : {r.get('expense_type')}")
            print(f"       Vendor    : {r.get('vendor')}")
            print(f"       Amount    : {r.get('currency')} {r.get('amount')}")
            print(f"       Date      : {r.get('transaction_date')}")
            print(f"       City      : {r.get('city')}")

            if r.get("airfare_detail"):
                ad = r["airfare_detail"]
                print(f"       ✈  {ad.get('origin')} → {ad.get('destination')}  |  {ad.get('airline')}  |  PNR: {ad.get('ticket_number')}  |  Class: {ad.get('travel_class')}  |  Passenger: {ad.get('passenger_name')}")

            if r.get("hotel_detail"):
                hd = r["hotel_detail"]
                print(f"       🏨  Check-in: {hd.get('check_in_date')}  →  Check-out: {hd.get('check_out_date')}  |  {hd.get('num_nights')} nights  @  {r.get('currency')} {hd.get('nightly_rate')}/night  |  Tax: {hd.get('tax_amount')}")

            if r.get("taxi_detail"):
                td = r["taxi_detail"]
                print(f"       🚕  {td.get('from_location')} → {td.get('to_location')}  |  {td.get('distance_km')} km")

            if r.get("meal_detail"):
                md = r["meal_detail"]
                print(f"       🍽  {md.get('meal_type')}  |  {md.get('num_attendees')} person(s)  |  {md.get('business_justification')}")
        else:
            print(f"       Error: {r.get('error_message')}")
        print()


if __name__ == "__main__":
    main()
