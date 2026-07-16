"""
generate_emp002_receipts.py
---------------------------
Generates sample receipt PDFs for EMP002 (Arjun Mehta) — Hyderabad trip.

Card transactions to match (TRIP003: 2026-07-15 to 2026-07-18):
  CCT007  Taj Hotels        INR 15,000   2026-07-15
  CCT008  Air India         INR  6,200   2026-07-14
  CCT009  Rapido            INR    420   2026-07-15
  CCT010  Paradise Biryani  INR    800   2026-07-16

Files produced (in data/sample_receipts/):
  emp002_taj_hotels.pdf          — hotel receipt matching CCT007
  emp002_air_india.pdf           — flight receipt matching CCT008
  emp002_rapido.pdf              — taxi receipt matching CCT009
  emp002_paradise_biryani.pdf    — meals receipt matching CCT010
  emp002_taj_hotels_dup.pdf      — exact duplicate of emp002_taj_hotels.pdf
  emp002_air_india_dup.pdf       — exact duplicate of emp002_air_india.pdf

Usage:
    pip install reportlab
    python data/generate_emp002_receipts.py
"""

from __future__ import annotations

from pathlib import Path


def _write_pdf(path: Path, lines: list[str]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    y = 780
    for line in lines:
        bold = line.startswith("**")
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 11)
        c.drawString(60, y, line.lstrip("*"))
        y -= 18
        if y < 60:
            c.showPage()
            y = 780
    c.save()


# ── Receipt content definitions ───────────────────────────────────────────────

def _taj_hotels_content() -> list[str]:
    """
    Hotel receipt — Taj Hotels Hyderabad
    Matches CCT007: INR 15,000 on 2026-07-15
    Trip: 2026-07-15 to 2026-07-17 (2 nights × INR 7,500 = INR 15,000)
    NOTE: nightly rate 7,500 exceeds STANDARD policy limit of 6,000 → triggers warning
    Total matches card transaction amount exactly (INR 15,000) — GST absorbed in rate.
    """
    return [
        "**TAJ HOTELS HYDERABAD",
        "**Banjara Hills, Road No. 1, Hyderabad 500034",
        "Tel: +91-40-6666-9999",
        "",
        "FOLIO / TAX INVOICE",
        "Invoice No  : THH-2026-00871",
        "Guest Name  : Arjun Mehta",
        "Room No     : 601",
        "",
        "Check-in    : 2026-07-15",
        "Check-out   : 2026-07-17",
        "No. of Nights : 2",
        "",
        "Room Charges    : INR 7,500.00 / night",
        "Room x 2 nights : INR 15,000.00",
        "------------------------------",
        "TOTAL PAYABLE   : INR 15,000.00",
        "",
        "Payment Mode: Corporate Card",
        "Card last 4 digits: 8888",
        "Employee ID : EMP002",
    ]


def _air_india_content() -> list[str]:
    """
    Flight receipt — Air India
    Matches CCT008: INR 6,200 on 2026-07-14
    """
    return [
        "**AIR INDIA",
        "e-Ticket / Booking Confirmation",
        "",
        "PNR           : AI-KL7294",
        "Ticket Number : 098-4567891234",
        "Booking Date  : 2026-07-10",
        "",
        "Passenger     : MEHTA/ARJUN MR",
        "Flight        : AI 543",
        "From          : BOM (Mumbai)",
        "To            : HYD (Hyderabad)",
        "Date          : 14 Jul 2026",
        "Departure     : 08:20",
        "Arrival       : 10:05",
        "Seat          : 22A",
        "Class         : Economy",
        "",
        "Base Fare     : INR 4,800.00",
        "Taxes & Fees  : INR 1,400.00",
        "------------------------------",
        "TOTAL         : INR 6,200.00",
        "",
        "Payment: Corporate Card ****8888",
        "Employee ID : EMP002",
    ]


def _rapido_content() -> list[str]:
    """
    Taxi receipt — Rapido
    Matches CCT009: INR 420 on 2026-07-15
    """
    return [
        "**RAPIDO",
        "Ride Receipt",
        "",
        "Booking ID  : RPD-HYD-20260715-55193",
        "Date        : 2026-07-15",
        "Time        : 11:10 AM",
        "",
        "Pickup  : Rajiv Gandhi International Airport, Hyderabad",
        "Drop    : Taj Hotels, Banjara Hills",
        "Distance: 32.6 km",
        "",
        "Base Fare   : INR 340.00",
        "Toll        : INR 60.00",
        "GST (5%)    : INR 20.00",
        "------------------------------",
        "TOTAL       : INR 420.00",
        "",
        "Payment: Corporate Card ****8888",
        "Employee ID : EMP002",
    ]


def _paradise_biryani_content() -> list[str]:
    """
    Meals receipt — Paradise Biryani
    Matches CCT010: INR 800 on 2026-07-16
    """
    return [
        "**PARADISE BIRYANI",
        "Paradise Circle, Secunderabad, Hyderabad",
        "GSTIN: 36ABCDE5678G1Z2",
        "",
        "Table : 7  |  Covers: 2",
        "Date  : 2026-07-16",
        "Time  : 1:30 PM",
        "",
        "Hyderabadi Dum Biryani (2) : INR 560",
        "Raita (2)                  : INR  80",
        "Cold Drinks (2)            : INR  80",
        "------------------------------",
        "Sub Total                  : INR 720",
        "GST (5%)                   : INR  36",
        "Service Charge (6%)        : INR  44",
        "------------------------------",
        "TOTAL                      : INR 800",
        "",
        "Payment: Corporate Card ****8888",
        "Business Purpose: Working lunch - tech conference",
        "Employee ID : EMP002",
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        from reportlab.lib.pagesizes import A4  # noqa: F401 — import check
    except ImportError:
        print("reportlab not installed. Run: pip install reportlab")
        return

    out_dir = Path(__file__).parent / "sample_receipts"
    out_dir.mkdir(parents=True, exist_ok=True)

    receipts = [
        # (filename,                       content_fn,              is_dup_of)
        ("emp002_taj_hotels.pdf",          _taj_hotels_content,     None),
        ("emp002_air_india.pdf",           _air_india_content,      None),
        ("emp002_rapido.pdf",              _rapido_content,         None),
        ("emp002_paradise_biryani.pdf",    _paradise_biryani_content, None),
        # Duplicates — identical content → same SHA-256 → triggers duplicate detection
        ("emp002_taj_hotels_dup.pdf",      _taj_hotels_content,     "emp002_taj_hotels.pdf"),
        ("emp002_air_india_dup.pdf",       _air_india_content,      "emp002_air_india.pdf"),
    ]

    print("Generating EMP002 receipt PDFs...\n")
    for filename, content_fn, dup_of in receipts:
        path = out_dir / filename
        _write_pdf(path, content_fn())
        if dup_of:
            print(f"  Created (duplicate of {dup_of}): {filename}")
        else:
            print(f"  Created: {filename}")

    print(f"\nGenerated {len(receipts)} PDFs in {out_dir}")
    print()
    print("Upload order for testing:")
    print("  1. emp002_taj_hotels.pdf        → matches CCT007 (Taj Hotels, INR 15,000, 2026-07-15)")
    print("  2. emp002_air_india.pdf         → matches CCT008 (Air India, INR 6,200, 2026-07-14)")
    print("  3. emp002_rapido.pdf            → matches CCT009 (Rapido, INR 420, 2026-07-15)")
    print("  4. emp002_paradise_biryani.pdf  → matches CCT010 (Paradise Biryani, INR 800, 2026-07-16)")
    print("  5. emp002_taj_hotels_dup.pdf    → DUPLICATE of #1 → should get status: duplicate")
    print("  6. emp002_air_india_dup.pdf     → DUPLICATE of #2 → should get status: duplicate")


if __name__ == "__main__":
    main()
