"""Central normalization helpers for bank reconciliation data.

Used by the classifier, matchers, and engine to ensure consistent
string handling before comparison.
"""

from __future__ import annotations

import re


def normalize_note(note: str | None) -> str:
    """Strip and collapse whitespace. Returns ``""`` for None/empty."""
    if not note:
        return ""
    return " ".join(note.strip().split())


_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]")


def normalize_payment_number(s: str | None) -> str | None:
    """Strip, remove non-alphanumeric chars. Returns None if empty."""
    if not s:
        return None
    cleaned = _NON_ALNUM_RE.sub("", s.strip())
    return cleaned if cleaned else None
