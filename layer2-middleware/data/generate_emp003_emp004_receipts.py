"""
generate_emp003_emp004_receipts.py
--------------------------------
Generates sample receipt PDFs for EMP003 and EMP004 with matching receipts only.
No duplicate files are created.

EMP003 card transactions to match (TRIP004: 2026-07-25 to 2026-07-28):
  CCT012  Leela Palace   INR 22,000   2026-07-25
  CCT013  Air India      INR 15,000   2026-07-24
  CCT014  Uber           INR  1,200   2026-07-25
  CCT015  Bukhara        INR  2,200   2026-07-26

EMP004 card transactions to match (TRIP005: 2026-08-01 to 2026-08-04):
  CCT016  ITC Gardenia   INR 19,500   2026-08-01
  CCT017  Vistara        INR  9,800   2026-07-31
  CCT018  Ola            INR    580   2026-08-01
  CCT019  Toit Brewpub   INR  1,800   2026-08-02

Files produced (in data/sample_receipts/):
  emp003_leela_palace.pdf
  emp003_air_india.pdf
  emp003_uber.pdf
  emp003_bukhara.pdf
  emp004_itc_gardenia.pdf
  emp004_vistara.pdf
  emp004_ola.pdf
  emp004_toit_brewpub.pdf

Usage:
    pip install reportlab
    python data/generate_emp003_emp004_receipts.py
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


def _emp003_leela_palace_content() -> list[str]:
    return [
        "**THE LEELA PALACE NEW DELHI",
        "Diplomatic Enclave, Chanakyapuri, New Delhi 110023",
        "Tel: +91-11-3933-1234",
        "",
        "HOTEL INVOICE",
        "Invoice No   : TLP-2026-1904",
        "Guest Name   : Kavita Nair",
        "Room No      : 845",
        "",
        "Check-in     : 2026-07-25",
        "Check-out    : 2026-07-27",
        "No. of Nights: 2",
        "",
        "Room Charges    : INR 11,000.00 / night",
        "Room x 2 nights : INR 22,000.00",
        "------------------------------",
        "TOTAL PAYABLE   : INR 22,000.00",
        "",
        "Payment Mode: Corporate Card",
        "Card last 4 digits: 1111",
        "Employee ID : EMP003",
    ]


def _emp003_air_india_content() -> list[str]:
    return [
        "**AIR INDIA",
        "e-Ticket / Booking Confirmation",
        "",
        "PNR           : AI-DL8821",
        "Ticket Number : 098-9988776655",
        "Booking Date  : 2026-07-18",
        "",
        "Passenger     : NAIR/KAVITA MS",
        "Flight        : AI 863",
        "From          : BLR (Bengaluru)",
        "To            : DEL (Delhi)",
        "Date          : 24 Jul 2026",
        "Departure     : 07:10",
        "Arrival       : 09:55",
        "Class         : Business",
        "",
        "Base Fare     : INR 12,700.00",
        "Taxes & Fees  : INR  2,300.00",
        "------------------------------",
        "TOTAL         : INR 15,000.00",
        "",
        "Payment: Corporate Card ****1111",
        "Employee ID : EMP003",
    ]


def _emp003_uber_content() -> list[str]:
    return [
        "**UBER",
        "Trip Receipt",
        "",
        "Trip ID      : UBR-DEL-20260725-7712",
        "Date         : 2026-07-25",
        "Time         : 11:45 AM",
        "",
        "Pickup       : Indira Gandhi International Airport",
        "Drop         : The Leela Palace New Delhi",
        "Distance     : 13.8 km",
        "",
        "Fare         : INR 1,050.00",
        "Toll         : INR   90.00",
        "GST          : INR   60.00",
        "------------------------------",
        "TOTAL        : INR 1,200.00",
        "",
        "Payment: Corporate Card ****1111",
        "Employee ID : EMP003",
    ]


def _emp003_bukhara_content() -> list[str]:
    return [
        "**BUKHARA",
        "ITC Maurya, Sardar Patel Marg, New Delhi",
        "GSTIN: 07ABCDE1234F1Z5",
        "",
        "Table : 14 | Covers: 2",
        "Date  : 2026-07-26",
        "Time  : 8:10 PM",
        "",
        "Dal Bukhara                 : INR  780",
        "Paneer Khurchan            : INR  640",
        "Naan Basket                : INR  320",
        "Beverages                  : INR  280",
        "------------------------------",
        "Sub Total                  : INR 2020",
        "GST + Service              : INR  180",
        "------------------------------",
        "TOTAL                      : INR 2200",
        "",
        "Payment: Corporate Card ****1111",
        "Employee ID : EMP003",
    ]


def _emp004_itc_gardenia_content() -> list[str]:
    return [
        "**ITC GARDENIA BENGALURU",
        "Residency Road, Bengaluru 560025",
        "Tel: +91-80-2211-9898",
        "",
        "HOTEL TAX INVOICE",
        "Invoice No   : ITC-2026-4411",
        "Guest Name   : Rohan Desai",
        "Room No      : 902",
        "",
        "Check-in     : 2026-08-01",
        "Check-out    : 2026-08-03",
        "No. of Nights: 2",
        "",
        "Room Charges    : INR 9,750.00 / night",
        "Room x 2 nights : INR 19,500.00",
        "------------------------------",
        "TOTAL PAYABLE   : INR 19,500.00",
        "",
        "Payment Mode: Corporate Card",
        "Card last 4 digits: 9999",
        "Employee ID : EMP004",
    ]


def _emp004_vistara_content() -> list[str]:
    return [
        "**VISTARA",
        "Booking Confirmation",
        "",
        "PNR           : UK-BL4402",
        "Ticket Number : 220-4455667788",
        "Booking Date  : 2026-07-25",
        "",
        "Passenger     : DESAI/ROHAN MR",
        "Flight        : UK 814",
        "From          : HYD (Hyderabad)",
        "To            : BLR (Bengaluru)",
        "Date          : 31 Jul 2026",
        "Departure     : 06:50",
        "Arrival       : 08:05",
        "Class         : Economy",
        "",
        "Base Fare     : INR 8,150.00",
        "Taxes & Fees  : INR 1,650.00",
        "------------------------------",
        "TOTAL         : INR 9,800.00",
        "",
        "Payment: Corporate Card ****9999",
        "Employee ID : EMP004",
    ]


def _emp004_ola_content() -> list[str]:
    return [
        "**OLA CABS",
        "Ride Receipt",
        "",
        "Booking ID   : OLA-BLR-20260801-2144",
        "Date         : 2026-08-01",
        "Time         : 09:10 AM",
        "",
        "Pickup       : Kempegowda International Airport",
        "Drop         : ITC Gardenia Bengaluru",
        "Distance     : 36.4 km",
        "",
        "Base Fare    : INR 470.00",
        "Airport Fee  : INR  60.00",
        "GST          : INR  50.00",
        "------------------------------",
        "TOTAL        : INR 580.00",
        "",
        "Payment: Corporate Card ****9999",
        "Employee ID : EMP004",
    ]


def _emp004_toit_brewpub_content() -> list[str]:
    return [
        "**TOIT BREWPUB",
        "100 Feet Road, Indiranagar, Bengaluru",
        "GSTIN: 29ABCDE9876K1Z8",
        "",
        "Table : 19 | Covers: 2",
        "Date  : 2026-08-02",
        "Time  : 8:25 PM",
        "",
        "Food & Beverages           : INR 1,620",
        "GST + Service              : INR   180",
        "------------------------------",
        "TOTAL                      : INR 1,800",
        "",
        "Payment: Corporate Card ****9999",
        "Employee ID : EMP004",
    ]


def main() -> None:
    try:
        from reportlab.lib.pagesizes import A4  # noqa: F401
    except ImportError:
        print("reportlab not installed. Run: pip install reportlab")
        return

    out_dir = Path(__file__).parent / "sample_receipts"
    out_dir.mkdir(parents=True, exist_ok=True)

    receipts = [
        ("emp003_leela_palace.pdf", _emp003_leela_palace_content),
        ("emp003_air_india.pdf", _emp003_air_india_content),
        ("emp003_uber.pdf", _emp003_uber_content),
        ("emp003_bukhara.pdf", _emp003_bukhara_content),
        ("emp004_itc_gardenia.pdf", _emp004_itc_gardenia_content),
        ("emp004_vistara.pdf", _emp004_vistara_content),
        ("emp004_ola.pdf", _emp004_ola_content),
        ("emp004_toit_brewpub.pdf", _emp004_toit_brewpub_content),
    ]

    print("Generating EMP003 and EMP004 receipt PDFs...\n")
    for filename, content_fn in receipts:
        path = out_dir / filename
        _write_pdf(path, content_fn())
        print(f"  Created: {filename}")

    print(f"\nGenerated {len(receipts)} PDFs in {out_dir}")


if __name__ == "__main__":
    main()
