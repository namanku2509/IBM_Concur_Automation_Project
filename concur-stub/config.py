from __future__ import annotations

"""
config.py
---------
Application settings loaded from environment variables (or a .env file).
All configuration that changes between environments lives here.
No business logic.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Runtime configuration for the SAP Concur Stub.

    Values are read from environment variables first, then from a .env file
    in the working directory, then from the defaults below.
    """

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #
    db_path: str = "concur_stub.db"
    """Path (relative or absolute) to the SQLite database file."""

    # ------------------------------------------------------------------ #
    # Authentication                                                       #
    # ------------------------------------------------------------------ #
    api_key: str = "concur-stub-dev-key"
    """
    Static API key expected in the X-Api-Key request header.
    Layer 2 (Orchestrate Skills) must include this header on every call.
    Swap for OAuth when pointing at the real SAP Concur APIs.
    """

    # ------------------------------------------------------------------ #
    # File storage                                                         #
    # ------------------------------------------------------------------ #
    receipts_store_dir: str = "receipts_store"
    """
    Directory for receipt metadata artefacts.
    The stub never stores raw receipt images — Layer 2 owns those.
    This directory holds any supplementary reference files if needed.
    """

    # ------------------------------------------------------------------ #
    # Application metadata                                                 #
    # ------------------------------------------------------------------ #
    app_title: str = "SAP Concur Stub"
    app_version: str = "1.0.0"
    app_description: str = (
        "A lightweight FastAPI stub that simulates the SAP Concur v4 REST API "
        "for the IBM watsonx AI Expense Claims Copilot prototype. "
        "Implements the business validation pipeline, travel policy enforcement, "
        "corporate card matching, hotel itemization, and audit logging."
    )

    # ------------------------------------------------------------------ #
    # Business rules                                                       #
    # ------------------------------------------------------------------ #
    card_match_date_tolerance_days: int = 2
    """
    How many calendar days either side of the expense transaction date
    to search for a matching corporate card transaction.
    Reflects real-world card posting delays and OCR date uncertainty.
    """

    trip_date_tolerance_days: int = 1
    """
    Buffer days added to each end of a trip's date window when matching
    expense dates against the trip. Accounts for travel days.
    """

    itemization_sum_tolerance: float = 1.0
    """
    Maximum acceptable rounding difference (in the expense's currency)
    between the sum of hotel itemization lines and the parent expense amount
    before a ITEMIZATION_SUM_MISMATCH warning is raised.
    """

    ocr_confidence_default_threshold: float = 0.75
    """
    Default minimum OCR confidence score (0.0–1.0) below which the
    LOW_OCR_CONFIDENCE warning is raised. Can be overridden per policy rule.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Module-level singleton — import this everywhere settings are needed.
settings = Settings()

# Ensure the receipts store directory exists at import time.
Path(settings.receipts_store_dir).mkdir(parents=True, exist_ok=True)
