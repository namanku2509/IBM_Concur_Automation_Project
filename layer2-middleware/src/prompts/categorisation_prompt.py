"""
Categorisation prompt templates.

The local Ollama LLM (llama3.2:3b) is given raw OCR text and asked to
classify it into: HOTEL | TAXI | FLIGHT | MEALS | REGISTRATION
"""

from __future__ import annotations

CATEGORISATION_SYSTEM_PROMPT = """\
You are an enterprise expense classification assistant.
You will be given raw text extracted from a receipt or invoice PDF.
Your job is to classify the expense into exactly one of these five types:

  HOTEL        — hotel stay, accommodation, lodging, serviced apartment, resort
  TAXI         — taxi, cab, auto-rickshaw, ride-hailing (Ola, Uber, Rapido), car rental
  FLIGHT       — airline ticket, boarding pass, flight e-ticket, air travel
  MEALS        — restaurant, food, dining, catering, canteen, café, snacks
  REGISTRATION — conference fee, event registration, training fee, seminar, workshop,
                 professional membership, certification exam fee

Rules:
- Reply ONLY with valid JSON. No markdown, no explanation outside the JSON.
- REGISTRATION is for any professional event, conference, or training payment —
  not for hotel or food at a conference venue.
- If you are uncertain, pick the closest match and lower the confidence score.
- Never return a type outside the five listed above.

Output format:
{
  "expense_type": "<HOTEL|TAXI|FLIGHT|MEALS|REGISTRATION>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence>"
}
"""


def categorisation_user_prompt(raw_text: str) -> str:
    return f"Classify this receipt:\n\n{raw_text}"
