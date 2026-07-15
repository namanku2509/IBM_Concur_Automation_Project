"""
tests/test_duplicate_detection.py
-----------------------------------
Unit tests for services/duplicate_detection.py.

compute_receipt_hash() is a pure function — tested with no DB.
is_duplicate() requires a DB session — tested with an in-memory SQLite fixture.
"""

from __future__ import annotations

import pytest

from services.duplicate_detection import compute_receipt_hash, is_duplicate


# ------------------------------------------------------------------ #
# compute_receipt_hash — pure function tests                           #
# ------------------------------------------------------------------ #

class TestComputeReceiptHash:
    def test_returns_64_char_hex(self):
        h = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP001")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        h1 = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP001")
        h2 = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP001")
        assert h1 == h2

    def test_vendor_case_insensitive(self):
        h1 = compute_receipt_hash("marriott",  18000.0, "2026-07-21", "EMP001")
        h2 = compute_receipt_hash("MARRIOTT",  18000.0, "2026-07-21", "EMP001")
        h3 = compute_receipt_hash("Marriott",  18000.0, "2026-07-21", "EMP001")
        assert h1 == h2 == h3

    def test_different_amounts_produce_different_hashes(self):
        """Split-bill scenario: same vendor/date but different amounts."""
        h1 = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP001")
        h2 = compute_receipt_hash("Marriott",  9000.0, "2026-07-21", "EMP001")
        assert h1 != h2

    def test_different_employees_produce_different_hashes(self):
        """Same expense details for two different employees — not a duplicate."""
        h1 = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP001")
        h2 = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP002")
        assert h1 != h2

    def test_different_dates_produce_different_hashes(self):
        h1 = compute_receipt_hash("Marriott", 18000.0, "2026-07-21", "EMP001")
        h2 = compute_receipt_hash("Marriott", 18000.0, "2026-07-22", "EMP001")
        assert h1 != h2

    def test_vendor_whitespace_normalised(self):
        h1 = compute_receipt_hash("  Marriott  ", 18000.0, "2026-07-21", "EMP001")
        h2 = compute_receipt_hash("Marriott",     18000.0, "2026-07-21", "EMP001")
        assert h1 == h2
