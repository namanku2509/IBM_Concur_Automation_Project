"""
Extraction prompt templates — one per expense type.

Each template provides:
  1. The raw OCR text
  2. The target JSON schema with Layer 3 DB field names and plain-English descriptions
  3. An explicit instruction to handle format variance across vendors

Sent to the local Ollama LLM (llama3.2:3b) — no API key needed.
"""

from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """\
You are an enterprise expense data extraction assistant.
You will be given raw text extracted from a receipt PDF and told which type of expense it is.
Your job is to extract structured data and map it to the exact JSON schema provided.

Rules:
- Reply ONLY with valid JSON matching the schema below. No markdown fences, no extra keys.
- Receipts have NO standard format. Different vendors use different words for the same field.
  Reason about synonyms and context — map any synonym to its correct schema field:
    * check-in synonyms : Arrival, Check In, From, Start Date, Valid From, Date of Stay
    * check-out synonyms: Departure, Check Out, Until, End Date, To, Return
    * amount synonyms   : Total, Grand Total, Amount Paid, Fare, Bill Amount, Payable, Charges
    * date synonyms     : Journey Date, Travel Date, Ride Date, Invoice Date, Transaction Date
    * vendor synonyms   : Property, Merchant, Operator, Issued By, Service Provider
- Dates appearing in cancellation policies (e.g. "Cancel before June 5") often ARE the check-in date.
- For distance: look for 'kilometres', 'kms', 'km', 'miles' anywhere in the text.
- For amounts: if multiple amounts appear, pick the largest final total, not a subtotal.
- Any field you genuinely cannot find must be null — never fabricate values.
- The "amount" field must never be null. If truly unclear, return 0.0.
- The "currency" field defaults to "INR" if the symbol is ₹ or context is India.
- All dates must be in YYYY-MM-DD format regardless of how they appear on the receipt.
  Parse formats like: '8 Jun 2026', 'Jun 8', '6/6/26', '2026-06-08', 'Mon, Jun 8' — all → YYYY-MM-DD.
"""


# ── Per-type schema descriptions ─────────────────────────────────────────────

_HOTEL_SCHEMA = """{
  "vendor":           "Hotel or property name. Look for: hotel name, property name, 'Property:', letterhead.",
  "amount":           "Total amount charged. Look for: 'Total', 'Grand Total', 'Amount Paid', 'Booking Value', 'Room Charges', 'Rate'. If only a nightly rate is shown, multiply by num_nights. If the document is a booking confirmation with no amount, return 0.0.",
  "currency":         "3-letter ISO code — infer from symbol: ₹=INR, $=USD, €=EUR. Default INR.",
  "transaction_date": "Check-out date — YYYY-MM-DD. Use check-out date if available, else invoice date.",
  "city":             "City name only — NOT the full address. Extract just the city name, e.g. 'Bangalore' or 'Mumbai'. If only a full address is available, pick the city part from it.",
  "check_in_date":    "Date of arrival — YYYY-MM-DD. Look for: 'Check-in', 'Arrival', 'Check In', 'From', 'Valid from', date mentioned before a dash in date ranges like 'Jun 5 - Jun 7'. Also look in cancellation policy text like 'Cancel before June 5' — that date IS the check-in date.",
  "check_out_date":   "Date of departure — YYYY-MM-DD. Look for: 'Check-out', 'Departure', 'Check Out', 'Until', the second date in a range like 'Jun 5 - Jun 7'.",
  "num_nights":       "Number of nights stayed — integer. Compute as (check_out - check_in).days if not stated explicitly.",
  "nightly_rate":     "Per-night room rate — float. Look for: 'Rate', 'Per Night', 'Room Rate', 'Nightly Rate'. If not shown, compute as (total_room_charges / num_nights).",
  "tax_amount":       "Sum of all taxes, GST, and service charges — float, 0.0 if not shown"
}"""

_TAXI_SCHEMA = """{
  "vendor":           "Taxi company or ride type — e.g. 'Uber Go', 'Uber Auto', 'Ola Mini', 'Rapido Bike'. Include both brand and vehicle type if shown.",
  "amount":           "Total fare. Look for: 'Total', 'Amount', 'Fare'. Use the final charged amount.",
  "currency":         "3-letter ISO code — ₹ or INR = INR",
  "transaction_date": "Date of the ride — YYYY-MM-DD. Look for: explicit date, or parse from timestamps like '6/6/26 8:17pm' = 2026-06-06, '2026-06-06', 'Jun 6 2026'.",
  "city":             "City where the ride took place — extract from addresses if not stated explicitly.",
  "from_location":    "Pickup location — full address or landmark as shown on the receipt.",
  "to_location":      "Drop location — full address or landmark as shown on the receipt. Note: on Uber receipts the FIRST location listed under 'Trip details' is the DROP (destination), the SECOND is the PICKUP. Read carefully.",
  "distance_km":      "Distance in km — float. Scan the ENTIRE receipt text for any number followed by 'km', 'kms', 'kilometres', 'kilometer', 'miles'. Examples: '8.32 kilometres' → 8.32, '12 km' → 12.0, '5.4 kms' → 5.4. This number is often inside a trip summary line. Extract just the numeric value. Null only if no distance unit appears anywhere."
}"""

_FLIGHT_SCHEMA = """{
  "vendor":           "Airline name — IndiGo, Air India, Air India Express, SpiceJet, Vistara, etc.",
  "amount":           "FINAL total ticket price actually charged. PRIORITY ORDER: (1) Look for 'TOTAL FARE', 'Total Fare', 'TOTAL AMOUNT', 'Amount Paid', 'Grand Total' label — use that exact value. (2) If no explicit total label, sum Base Fare + Taxes only. (3) NEVER pick a subtotal, base fare alone, or convenience fee alone. On IndiGo receipts 'TOTAL FARE' is the correct field. If Base Fare is 4200 and Taxes are 1300, TOTAL FARE is 5500 — use 5500.",
  "currency":         "3-letter ISO code — ₹ or INR = INR",
  "transaction_date": "Date of travel (departure date) — YYYY-MM-DD. Look for departure date, travel date, or journey date.",
  "city":             "Full departure city name (not airport code). E.g. if origin is BLR, city is Bengaluru.",
  "origin":           "Origin as 'City Name (IATA)' format where possible, e.g. 'Bengaluru (BLR)'. If only city name is shown use that. If only IATA code is shown, expand it: BLR=Bengaluru, DEL=Delhi, BOM=Mumbai, CCU=Kolkata, MAA=Chennai, HYD=Hyderabad, IXR=Ranchi, AMD=Ahmedabad, GOI=Goa, COK=Kochi.",
  "destination":      "Destination as 'City Name (IATA)' format where possible. Apply same IATA expansion rules as origin.",
  "airline":          "Full airline name as printed on the ticket",
  "ticket_number":    "PNR, booking reference, or e-ticket number — alphanumeric code on the ticket",
  "travel_class":     "Travel class — Economy, Business, or First. Default Economy if not shown.",
  "passenger_name":   "Full name of the passenger as printed on the ticket"
}"""

_MEALS_SCHEMA = """{
  "vendor":                "Restaurant or establishment name",
  "amount":                "Total bill amount including taxes and service charge",
  "currency":              "3-letter ISO code",
  "transaction_date":      "Date of the meal — YYYY-MM-DD",
  "city":                  "City where the meal took place",
  "meal_type":             "breakfast, lunch, dinner, or snack — infer from time if shown",
  "num_attendees":         "Number of people — integer, 1 if not shown",
  "business_justification":"Business reason for the meal — null if not shown"
}"""

_REGISTRATION_SCHEMA = """{
  "vendor":           "Organisation or company that issued the receipt — conference organiser, training provider",
  "amount":           "Total amount paid including taxes",
  "currency":         "3-letter ISO code",
  "transaction_date": "Date of payment or registration — YYYY-MM-DD",
  "city":             "City where the event takes place",
  "event_name":       "Full name of the conference, seminar, training, or event",
  "event_date":       "Date the event takes place (not payment date) — YYYY-MM-DD, null if not shown",
  "registration_id":  "Registration ID, booking reference, or delegate ID",
  "organiser":        "Name of the organising body or institution"
}"""

_SCHEMAS: dict[str, str] = {
    "HOTEL":        _HOTEL_SCHEMA,
    "TAXI":         _TAXI_SCHEMA,
    "FLIGHT":       _FLIGHT_SCHEMA,
    "MEALS":        _MEALS_SCHEMA,
    "REGISTRATION": _REGISTRATION_SCHEMA,
}


def extraction_user_prompt(raw_text: str, expense_type: str) -> str:
    schema = _SCHEMAS.get(expense_type, _MEALS_SCHEMA)
    return (
        f"Expense type: {expense_type}\n\n"
        f"Target JSON schema (extract exactly these fields):\n{schema}\n\n"
        f"Receipt text:\n{raw_text}\n\n"
        "Extract the data and return only the JSON object."
    )
