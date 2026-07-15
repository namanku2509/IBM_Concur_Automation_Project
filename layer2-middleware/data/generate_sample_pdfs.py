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
        ("hotel_marriott.pdf", _hotel_content()),
        ("taxi_ola.pdf", _taxi_content()),
        ("flight_indigo.pdf", _flight_content()),
        ("meals_restaurant.pdf", _meals_content()),
        ("meals_conference.pdf", _conference_content()),
        ("misc_pharmacy.pdf", _pharmacy_content()),
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


def _hotel_content():
    return [
        "**MARRIOTT BENGALURU",
        "**No. 12, Vittal Mallya Road, Bengaluru 560001",
        "Tel: +91-80-2214-9000",
        "",
        "FOLIO / TAX INVOICE",
        "Invoice No : MBL-2026-00421",
        "Guest Name : Rahul Sharma",
        "Room No    : 412",
        "",
        "Check-in   : 2026-07-19",
        "Check-out  : 2026-07-21",
        "No. of Nights : 2",
        "",
        "Room Charges    : INR 4,500.00 / night",
        "Room x 2 nights : INR 9,000.00",
        "GST (12%)       : INR 1,080.00",
        "Service Charge  : INR 450.00",
        "------------------------------",
        "TOTAL PAYABLE   : INR 10,530.00",
        "",
        "Payment Mode: Corporate Card",
        "Card last 4 digits: 4242",
    ]


def _taxi_content():
    return [
        "**OLA CABS",
        "Ride Receipt",
        "",
        "Booking ID  : OLA-BLR-20260721-88421",
        "Date        : 2026-07-21",
        "Time        : 09:35 AM",
        "",
        "Pickup  : Marriott Bengaluru, Vittal Mallya Road",
        "Drop    : Kempegowda International Airport",
        "Distance: 38.4 km",
        "",
        "Base Fare   : INR 380.00",
        "Toll        : INR 40.00",
        "GST (5%)    : INR 21.00",
        "------------------------------",
        "TOTAL       : INR 441.00",
        "",
        "Payment: Corporate Card ****4242",
    ]


def _flight_content():
    return [
        "**IndiGo",
        "e-Ticket / Booking Confirmation",
        "",
        "PNR            : 6E-WX842",
        "Ticket Number  : 423-1234567890",
        "Booking Date   : 2026-07-15",
        "",
        "Passenger      : SHARMA/RAHUL MR",
        "Flight         : 6E 501",
        "From           : BLR (Bengaluru)",
        "To             : BOM (Mumbai)",
        "Date           : 21 Jul 2026",
        "Departure      : 11:40",
        "Arrival        : 13:15",
        "Seat           : 14C",
        "Class          : Economy",
        "",
        "Base Fare      : INR 3,200.00",
        "Taxes & Fees   : INR 680.00",
        "------------------------------",
        "TOTAL          : INR 3,880.00",
        "",
        "Payment: Corporate Card ****4242",
    ]


def _meals_content():
    return [
        "**MAINLAND CHINA",
        "No. 8, Residency Road, Bengaluru",
        "GSTIN: 29ABCDE1234F1Z5",
        "",
        "Table : 12  |  Covers: 3",
        "Date  : 2026-07-20",
        "Time  : 8:45 PM",
        "",
        "Veg Spring Roll (2)       :  INR 320",
        "Kung Pao Chicken          :  INR 540",
        "Steamed Rice (3)          :  INR 240",
        "Mocktails (3)             :  INR 510",
        "------------------------------",
        "Sub Total                 : INR 1,610",
        "GST (5%)                  :   INR  80",
        "Service Charge (10%)      :  INR 161",
        "------------------------------",
        "TOTAL                     : INR 1,851",
        "",
        "Payment: Corporate Card ****4242",
        "Business Purpose: Team dinner - client meeting",
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
