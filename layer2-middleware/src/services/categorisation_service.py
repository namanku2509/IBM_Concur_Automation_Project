"""
Categorisation service — Ollama (local LLM, no API key needed).

Uses llama3.2:3b running locally via Ollama to classify raw OCR text
into one of: HOTEL | TAXI | FLIGHT | MEALS

Falls back to keyword classifier if Ollama is not running.

Start Ollama before running:
    ollama serve          (in a separate terminal)
    ollama pull llama3.2:3b
"""

from __future__ import annotations

import json
import logging
import re

from src import config
from src.models.receipt_models import CategorisationResult
from src.prompts.categorisation_prompt import (
    CATEGORISATION_SYSTEM_PROMPT,
    categorisation_user_prompt,
)

logger = logging.getLogger(__name__)

_VALID_TYPES = {"HOTEL", "TAXI", "FLIGHT", "MEALS", "REGISTRATION"}


async def categorise(raw_text: str) -> CategorisationResult:
    """
    Stage 2 — Categorise expense type using local Ollama LLM.
    Falls back to keyword classifier if Ollama is not running.
    """
    if not config.ollama_configured():
        logger.warning(
            "Ollama not running — using keyword fallback. "
            "Start Ollama: ollama serve && ollama pull llama3.2:3b"
        )
        return _keyword_fallback(raw_text)

    try:
        raw_response = _call_ollama(raw_text)
        parsed = _extract_json(raw_response)

        expense_type = str(parsed.get("expense_type", "")).upper()
        if expense_type not in _VALID_TYPES:
            logger.warning("Ollama returned unknown type '%s' — using keyword fallback", expense_type)
            return _keyword_fallback(raw_text)

        confidence = float(parsed.get("confidence", 0.85))
        reasoning = parsed.get("reasoning")

        logger.info("Categorised: %s (confidence=%.2f)", expense_type, confidence)
        return CategorisationResult(
            expense_type=expense_type,
            confidence=confidence,
            reasoning=reasoning,
        )

    except Exception as exc:
        logger.warning("Ollama categorisation failed: %s — using keyword fallback", exc)
        return _keyword_fallback(raw_text)


def _call_ollama(raw_text: str) -> str:
    """Call local Ollama server and return raw response string."""
    try:
        import ollama
    except ImportError:
        raise RuntimeError("ollama package not installed. Run: pip install ollama")

    prompt = f"{CATEGORISATION_SYSTEM_PROMPT}\n\n{categorisation_user_prompt(raw_text)}"

    response = ollama.generate(
        model=config.OLLAMA_MODEL,
        prompt=prompt,
        options={
            "temperature": config.OLLAMA_PARAMS["temperature"],
            "num_predict": config.OLLAMA_PARAMS["num_predict"],
        },
    )
    result = response.get("response", "")
    logger.debug("Ollama categorisation response: %s", result[:200])
    return result


def _extract_json(raw: str) -> dict:
    """Extract JSON object from LLM response, handling markdown fences."""
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence_match:
        raw = fence_match.group(1)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed: %s", exc)
    return {}


def _keyword_fallback(raw_text: str) -> CategorisationResult:
    """Deterministic keyword-based classifier — works with zero dependencies."""
    text_lower = raw_text.lower()

    hotel_keywords = (
        "hotel", "inn", "resort", "suites", "lodge", "accommodation",
        "check-in", "check-out", "room rate", "folio", "nightly", "nights",
    )
    taxi_keywords = (
        "ola", "uber", "rapido", "taxi", "cab", "auto",
        "ride", "pickup", "drop", "fare", "toll", "km",
    )
    flight_keywords = (
        "flight", "airline", "indigo", "air india", "spicejet", "vistara",
        "boarding", "pnr", "departure", "arrival", "airfare", "e-ticket",
    )
    meal_keywords = (
        "restaurant", "cafe", "diner", "food", "meal", "lunch", "dinner",
        "breakfast", "snack", "menu", "service charge", "zomato", "swiggy",
    )
    registration_keywords = (
        "registration", "conference", "seminar", "workshop", "training",
        "delegate", "forum", "summit", "symposium", "certification",
        "membership", "registration fee", "registration id", "event",
    )

    scores = {
        "HOTEL":        sum(1 for k in hotel_keywords if k in text_lower),
        "TAXI":         sum(1 for k in taxi_keywords if k in text_lower),
        "FLIGHT":       sum(1 for k in flight_keywords if k in text_lower),
        "MEALS":        sum(1 for k in meal_keywords if k in text_lower),
        "REGISTRATION": sum(1 for k in registration_keywords if k in text_lower),
    }

    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]
    total = sum(scores.values()) or 1
    confidence = round(min(best_score / total, 0.9), 2) if best_score > 0 else 0.4

    if best_score == 0:
        best = "MEALS"
        confidence = 0.4

    logger.info("Keyword fallback: %s (confidence=%.2f) scores=%s", best, confidence, scores)
    return CategorisationResult(
        expense_type=best,
        confidence=confidence,
        reasoning="Keyword fallback — Ollama not running.",
    )
