"""
Hash service — SHA-256 utility.

Reused by ocr_service (file hash) and schema_mapper (receipt_hash field).
"""

from __future__ import annotations

import hashlib


def compute_sha256(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()
