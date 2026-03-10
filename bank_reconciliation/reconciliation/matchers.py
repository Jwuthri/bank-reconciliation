"""Matchers that pair bank transactions with EOBs.

Matcher 1 — PaymentNumberMatcher:
    Extracts the payment number from the TRN segment in HCCLAIMPMT notes
    (format: ``TRN*1*<PAYMENT_NUMBER>*…``) and looks it up against EOB
    payment_number.  Confidence is 1.0 for exact amount match, 0.9 when
    the amount is within a small fee tolerance.

Matcher 2 — PayerAmountDateMatcher:
    For transactions whose note identifies a payer (MetLife, Guardian Life,
    CALIFORNIA DENTA), matches on payer + abs(amount) == adjusted_amount
    within a configurable date window.  Unique match → 0.85 confidence;
    ambiguous (multiple candidates) → 0.7, picking the closest date.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, Sequence

from bank_reconciliation.reconciliation.normalize import (
    normalize_note,
    normalize_payment_number,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TRN extraction
# ---------------------------------------------------------------------------

_TRN_RE = re.compile(r"TRN\*1\*([^*]+)\*")


def extract_trn_payment_number(note: str | None) -> str | None:
    """Extract payment number from ``TRN*1*<NUM>*…`` in a bank note."""
    if not note:
        return None
    m = _TRN_RE.search(note)
    if not m:
        return None
    return normalize_payment_number(m.group(1))


# ---------------------------------------------------------------------------
# Match result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MatchResult:
    eob_id: int
    bank_transaction_id: int
    confidence: float  # 0.0–1.0
    match_method: str


# ---------------------------------------------------------------------------
# Protocols for duck-typing DB models in tests
# ---------------------------------------------------------------------------


class BankTransactionLike(Protocol):
    id: int
    amount: int
    note: str | None
    received_at: object  # datetime


class EOBLike(Protocol):
    id: int
    payment_number: str | None
    payer_id: int
    adjusted_amount: int
    payment_date: object  # datetime


class Matcher(Protocol):
    """Protocol for matchers that pair bank transactions with EOBs."""

    def match(
        self,
        transactions: Sequence[BankTransactionLike],
        *,
        already_matched_eob_ids: set[int] | None = None,
        already_matched_txn_ids: set[int] | None = None,
    ) -> list[MatchResult]: ...


# ---------------------------------------------------------------------------
# PaymentNumberMatcher
# ---------------------------------------------------------------------------

# Maximum absolute difference (in cents) to still accept as a fee-tolerance match.
_FEE_TOLERANCE_CENTS = 500


class PaymentNumberMatcher:
    """Match HCCLAIMPMT transactions to EOBs via the TRN payment number."""

    def __init__(self, eobs: Sequence[EOBLike]) -> None:
        self._eob_by_payment_number: dict[str, EOBLike] = {}
        for eob in eobs:
            key = normalize_payment_number(eob.payment_number)
            if key:
                if key in self._eob_by_payment_number:
                    logger.warning(
                        "Duplicate payment_number %r: EOB %d overwrites EOB %d",
                        key,
                        eob.id,
                        self._eob_by_payment_number[key].id,
                    )
                self._eob_by_payment_number[key] = eob

    def match(
        self,
        transactions: Sequence[BankTransactionLike],
        *,
        already_matched_eob_ids: set[int] | None = None,
        already_matched_txn_ids: set[int] | None = None,
    ) -> list[MatchResult]:
        matched_eob_ids = set(already_matched_eob_ids or ())
        skip_txn_ids = already_matched_txn_ids or set()
        results: list[MatchResult] = []

        for bt in transactions:
            if bt.id in skip_txn_ids:
                continue

            payment_num = extract_trn_payment_number(bt.note)
            if payment_num is None:
                continue

            eob = self._eob_by_payment_number.get(payment_num)
            if eob is None or eob.id in matched_eob_ids:
                continue

            diff = abs(abs(bt.amount) - eob.adjusted_amount)
            if diff == 0:
                confidence = 1.0
            elif diff <= _FEE_TOLERANCE_CENTS:
                confidence = 0.9
            else:
                continue

            results.append(
                MatchResult(
                    eob_id=eob.id,
                    bank_transaction_id=bt.id,
                    confidence=confidence,
                    match_method="payment_number",
                )
            )
            matched_eob_ids.add(eob.id)

        return results


# ---------------------------------------------------------------------------
# PayerAmountDateMatcher
# ---------------------------------------------------------------------------

def build_payer_note_map_from_db(payers: Sequence[object]) -> dict[int, str]:
    """Build payer_note_map from Payer rows.

    Uses PAYER_NAME_TO_NOTE_PATTERN from payer_registry to map payer names
    to note patterns for matching.
    """
    from bank_reconciliation.reconciliation.payer_registry import PAYER_NAME_TO_NOTE_PATTERN

    result: dict[int, str] = {}
    for p in payers:
        payer_name_lower = p.name.lower()  # type: ignore[union-attr]
        for name_prefix, pattern in PAYER_NAME_TO_NOTE_PATTERN.items():
            if payer_name_lower.startswith(name_prefix.lower()):
                result[p.id] = pattern  # type: ignore[union-attr]
                break
    return result


class PayerAmountDateMatcher:
    """Match transactions to EOBs by payer name + amount + date proximity."""

    def __init__(
        self,
        eobs: Sequence[EOBLike],
        *,
        payer_note_map: dict[int, str],
        date_window_days: int = 14,
    ) -> None:
        self._payer_note_map = payer_note_map
        self._date_window = timedelta(days=date_window_days)

        # Reverse map: note pattern → payer_id
        self._note_to_payer: list[tuple[str, int]] = [
            (pattern, pid) for pid, pattern in self._payer_note_map.items()
        ]

        # Index EOBs by (payer_id, adjusted_amount) for fast lookup
        self._eob_index: dict[tuple[int, int], list[EOBLike]] = {}
        for eob in eobs:
            key = (eob.payer_id, eob.adjusted_amount)
            self._eob_index.setdefault(key, []).append(eob)

    def _identify_payer(self, note: str | None) -> int | None:
        """Return the payer_id if the note matches a known payer pattern."""
        normalized = normalize_note(note)
        if not normalized:
            return None
        note_upper = normalized.upper()
        for pattern, payer_id in self._note_to_payer:
            if pattern.upper() in note_upper:
                return payer_id
        return None

    def match(
        self,
        transactions: Sequence[BankTransactionLike],
        *,
        already_matched_eob_ids: set[int] | None = None,
        already_matched_txn_ids: set[int] | None = None,
    ) -> list[MatchResult]:
        matched_eob_ids = set(already_matched_eob_ids or ())
        skip_txn_ids = already_matched_txn_ids or set()
        results: list[MatchResult] = []

        for bt in transactions:
            if bt.id in skip_txn_ids:
                continue

            payer_id = self._identify_payer(bt.note)
            if payer_id is None:
                continue

            abs_amount = abs(bt.amount)
            candidates = self._eob_index.get((payer_id, abs_amount), [])

            # Filter by date window and already-matched
            eligible = [
                eob
                for eob in candidates
                if eob.id not in matched_eob_ids
                and abs(bt.received_at - eob.payment_date) <= self._date_window  # type: ignore[operator]
            ]

            if not eligible:
                continue

            if len(eligible) == 1:
                best = eligible[0]
                confidence = 0.85
            else:
                best = min(
                    eligible,
                    key=lambda e: abs(bt.received_at - e.payment_date),  # type: ignore[operator]
                )
                confidence = 0.7

            results.append(
                MatchResult(
                    eob_id=best.id,
                    bank_transaction_id=bt.id,
                    confidence=confidence,
                    match_method="payer_amount_date",
                )
            )
            matched_eob_ids.add(best.id)

        return results


