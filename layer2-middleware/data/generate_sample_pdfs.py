"""
generate_sample_pdfs.py — Creates 6 sample receipt PDFs for testing.

Requires reportlab: pip install reportlab

Usage:
    python data/generate_sample_pdfs.py
"""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        print("reportlab not installed. Run: pip install reportlab")
        return

    out_dir = Path(__file__).parent / "sample_receipts"
    out_dir.mkdir(parents=True, exist_ok=True)

    receipts = [
        # Named to match the 6 EMP001 card transactions (CCT001–CCT006)
        ("receipt_1_marriott_hotel_INR18000.pdf",  _hotel_marriott()),
        ("receipt_2_indigo_flight_INR5500.pdf",    _flight_indigo()),
        ("receipt_3_ola_cab_INR650.pdf",           _taxi_ola_650()),
        ("receipt_4_fattybao_meal_INR950.pdf",     _meals_fattybao()),
        ("receipt_5_ola_cab_INR720.pdf",           _taxi_ola_720()),
        ("receipt_6_uber_cab_INR999.pdf",          _taxi_uber()),
        # Extras kept for standalone testing
        ("hotel_marriott.pdf",                     _hotel_marriott()),
        ("taxi_ola.pdf",                           _taxi_ola_650()),
        ("flight_indigo.pdf",                      _flight_indigo()),
        ("meals_restaurant.pdf",                   _meals_fattybao()),
        ("meals_conference.pdf",                   _conference_content()),
        ("misc_pharmacy.pdf",                      _pharmacy_content()),
    ]

    for filename, lines in receipts:
        path = out_dir / filename
        c = canvas.Canvas(str(path), pagesize=A4)
        y = 780
        for line in lines:
            c.setFont("Helvetica-Bold" if line.startswith("**") else "Helvetica", 11)
            text = line.lstrip("*")
            c.drawString(60, y, text)
            y -= 18
            if y < 60:
                c.showPage()
                y = 780
        c.save()
        print(f"  Created: {path.name}")

    print(f"\nGenerated {len(receipts)} sample PDFs in {out_dir}")


# ── CCT001 — Marriott Hotel INR 18,000 (Check-in 2026-07-20) ─────────────────
def _hotel_marriott():
    return [
        "**MARRIOTT BENGALURU",
        "**No. 12, Vittal Mallya Road, Bengaluru 560001",
        "Tel: +91-80-2214-9000 | GSTIN: 29AAACM0025L1Z6",
        "",
        "FOLIO / TAX INVOICE",
        "Invoice No : MBL-2026-00842",
        "Guest Name : Priya Sharma",
        "Room No    : 1204",
        "",
        "Check-in   : 2026-07-20",
        "Check-out  : 2026-07-22",
        "No. of Nights : 2",
        "",
        "Room Rate       : INR 8,000.00 per night",
        "Room x 2 nights : INR 16,000.00",
        "GST (12%)       : INR  1,920.00",
        "Sundry Charges  : INR     80.00",
        "------------------------------",
        "TOTAL PAYABLE   : INR 18,000.00",
        "",
        "Payment Mode : Corporate Card ****4242",
        "City         : Bengaluru",
    ]


# ── CCT002 — IndiGo Flight INR 5,500 (Travel date 2026-07-19) ────────────────
def _flight_indigo():
    return [
        "**IndiGo",
        "e-Ticket / Booking Confirmation",
        "",
        "PNR            : FXBGH2",
        "Booking Ref    : 6E-20260719-001",
        "Booking Date   : 2026-07-10",
        "",
        "Passenger      : SHARMA/PRIYA MS",
        "Flight         : 6E 204",
        "From           : BLR (Bengaluru)",
        "To             : DEL (New Delhi)",
        "Travel Date    : 19 Jul 2026",
        "Departure      : 06:20",
        "Arrival        : 09:05",
        "Seat           : 24A",
        "Class          : Economy",
        "",
        "Base Fare      : INR 4,200.00",
        "Taxes & Fees   : INR 1,300.00",
        "------------------------------",
        "TOTAL FARE     : INR 5,500.00",
        "",
        "Payment: Corporate Card ****4242",
        "City: Bengaluru",
    ]


# ── CCT003 — Ola Cab INR 650 (Date 2026-07-20) ────────────────────────────────
def _taxi_ola_650():
    return [
        "**OLA CABS",
        "Ride Receipt",
        "",
        "Booking ID  : OLA-BLR-20260720-44123",
        "Date        : 2026-07-20",
        "Time        : 09:10 AM",
        "",
        "Pickup  : Kempegowda International Airport, Bengaluru",
        "Drop    : Marriott Hotel, Vittal Mallya Road, Bengaluru",
        "Distance: 42.3 km",
        "",
        "Base Fare   : INR 590.00",
        "Toll        : INR 45.00",
        "GST (5%)    : INR 15.00",
        "------------------------------",
        "TOTAL       : INR 650.00",
        "",
        "Payment: Corporate Card ****4242",
        "City: Bengaluru",
    ]


# ── CCT004 — The Fatty Bao INR 950 (Date 2026-07-21) ─────────────────────────
def _meals_fattybao():
    return [
        "**The Fatty Bao",
        "No. 4, Wood Street, Bengaluru 560025",
        "GSTIN: 29AABCF5678G1Z9",
        "",
        "Table : 7  |  Covers: 2",
        "Date  : 2026-07-21",
        "Time  : 8:30 PM",
        "",
        "Steamed Pork Baos (2)     : INR 380",
        "Asian Slaw Salad          : INR 280",
        "House Cocktails (2)       : INR 180",
        "------------------------------",
        "Sub Total                 : INR 840",
        "GST (5%)                  : INR  42",
        "Service Charge (8%)       : INR  68",
        "------------------------------",
        "TOTAL                     : INR 950",
        "",
        "Payment: Corporate Card ****4242",
        "City: Bengaluru",
        "Business Purpose: Client dinner",
    ]


# ── CCT005 — Ola Cab INR 720 (Date 2026-07-22) ────────────────────────────────
def _taxi_ola_720():
    return [
        "**OLA CABS",
        "Ride Receipt",
        "",
        "Booking ID  : OLA-BLR-20260722-99812",
        "Date        : 2026-07-22",
        "Time        : 04:45 AM",
        "",
        "Pickup  : Marriott Hotel, Vittal Mallya Road, Bengaluru",
        "Drop    : Kempegowda International Airport, Bengaluru",
        "Distance: 43.1 km",
        "",
        "Base Fare   : INR 645.00",
        "GST (5%)    : INR  32.00",
        "Toll        : INR  43.00",
        "------------------------------",
        "TOTAL       : INR 720.00",
        "",
        "Payment: Corporate Card ****4242",
        "City: Bengaluru",
    ]


# ── CCT006 — Uber Cab INR 999 (Date 2026-07-21) ───────────────────────────────
def _taxi_uber():
    return [
        "**Uber",
        "Trip Receipt",
        "",
        "Trip Date   : 2026-07-21",
        "Trip Time   : 3:15 PM",
        "Service     : Uber Go",
        "",
        "Pickup  : Indiranagar, Bengaluru",
        "Drop    : MG Road, Bengaluru",
        "Distance: 8.6 km",
        "",
        "Base Fare      : INR 899.00",
        "Booking Fee    : INR  50.00",
        "GST (5%)       : INR  50.00",
        "------------------------------",
        "TOTAL          : INR 999.00",
        "",
        "Payment: Corporate Card ****4242",
        "City: Bengaluru",
    ]



def _conference_content():
    return [
        "**NASSCOM INDIA LEADERSHIP FORUM 2026",
        "Registration Receipt",
        "",
        "Delegate        : Rahul Sharma",
        "Organisation    : IBM India Pvt Ltd",
        "Event           : NASSCOM India Leadership Forum 2026",
        "Venue           : Bengaluru International Exhibition Centre",
        "Date            : 2026-07-20",
        "",
        "Registration ID : NASSCOM-2026-ILF-4521",
        "",
        "Registration Fee : INR 8,500.00",
        "GST (18%)        : INR 1,530.00",
        "------------------------------",
        "TOTAL PAID       : INR 10,030.00",
        "",
        "Payment Mode: Corporate Card ****4242",
    ]


def _pharmacy_content():
    return [
        "**WELLNESS FOREVER",
        "MG Road, Bengaluru",
        "Ph: 080-41234567",
        "",
        "CASH MEMO / TAX INVOICE",
        "Invoice No : WF-BLR-20260720-0891",
        "Date       : 2026-07-20",
        "",
        "Paracetamol 500mg x 10    : INR  28.00",
        "ORS Sachet x 5            : INR  35.00",
        "Vitamin C 500mg x 30      : INR 145.00",
        "------------------------------",
        "Sub Total                 : INR 208.00",
        "GST                       : INR  10.40",
        "TOTAL                     : INR 218.40",
        "",
        "Payment: Cash",
        "Note: Medical expenses — travel illness",
    ]


if __name__ == "__main__":
    main()
