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
from datetime import datetime, timedelta
from typing import Protocol, Sequence

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
    return m.group(1) if m else None


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
            if eob.payment_number:
                if eob.payment_number in self._eob_by_payment_number:
                    logger.warning(
                        "Duplicate payment_number %r: EOB %d overwrites EOB %d",
                        eob.payment_number,
                        eob.id,
                        self._eob_by_payment_number[eob.payment_number].id,
                    )
                self._eob_by_payment_number[eob.payment_number] = eob

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

# Default mapping: payer_id → substring that appears in bank transaction notes.
# Callers can override via constructor arg or build from DB.
DEFAULT_PAYER_NOTE_MAP: dict[int, str] = {
    3: "MetLife",
    4: "Guardian Life",
    5: "CALIFORNIA DENTA",
}


def build_payer_note_map_from_db(payers: Sequence[object]) -> dict[int, str]:
    """Build payer_note_map from Payer rows.

    Uses known note patterns for payers that appear directly in bank notes.
    Override or extend as new payer patterns are discovered.
    """
    _KNOWN: dict[str, str] = {
        "MetLife": "MetLife",
        "Guardian": "Guardian Life",
        "Delta Dental": "CALIFORNIA DENTA",
        "California Dental": "CALIFORNIA DENTA",
    }
    result: dict[int, str] = {}
    for p in payers:
        for name_prefix, pattern in _KNOWN.items():
            if p.name.startswith(name_prefix):  # type: ignore[union-attr]
                result[p.id] = pattern  # type: ignore[union-attr]
                break
    return result


class PayerAmountDateMatcher:
    """Match transactions to EOBs by payer name + amount + date proximity."""

    def __init__(
        self,
        eobs: Sequence[EOBLike],
        *,
        payer_note_map: dict[int, str] | None = None,
        date_window_days: int = 14,
    ) -> None:
        self._payer_note_map = payer_note_map or DEFAULT_PAYER_NOTE_MAP
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
        if not note:
            return None
        note_upper = note.upper()
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


# ---------------------------------------------------------------------------
# Public API — run all matchers and persist
# ---------------------------------------------------------------------------


def match_all(
    *,
    overwrite: bool = False,
    batch_size: int = 500,
) -> list[MatchResult]:
    """Run all matchers against insurance-classified transactions and persist.

    Pipeline:
      1. Load insurance transactions (via TransactionClassification).
      2. Run PaymentNumberMatcher (highest confidence first).
      3. Run PayerAmountDateMatcher on remaining unmatched.
      4. Persist all results to ReconciliationMatch.

    Returns:
        All MatchResult objects produced.
    """
    from bank_reconciliation.db.models import (
        BankTransaction,
        EOB,
        Payer,
        ReconciliationMatch,
        TransactionClassification,
    )

    if overwrite:
        db = ReconciliationMatch._meta.database
        db.drop_tables([ReconciliationMatch])
        db.create_tables([ReconciliationMatch])
        logger.info("Overwrite: dropped and recreated reconciliation_matches")

    insurance_txn_ids = {
        row.bank_transaction_id
        for row in TransactionClassification.select(
            TransactionClassification.bank_transaction
        ).where(TransactionClassification.is_insurance == True)  # noqa: E712
    }

    transactions = list(
        BankTransaction.select().where(BankTransaction.id << list(insurance_txn_ids))
    )
    eobs = list(EOB.select())
    payers = list(Payer.select())

    logger.info(
        "Matching %d insurance transactions against %d EOBs",
        len(transactions),
        len(eobs),
    )

    # Stage 1: PaymentNumberMatcher
    pn_matcher = PaymentNumberMatcher(eobs)
    pn_results = pn_matcher.match(transactions)

    matched_eob_ids = {r.eob_id for r in pn_results}
    matched_txn_ids = {r.bank_transaction_id for r in pn_results}

    # Stage 2: PayerAmountDateMatcher
    payer_note_map = build_payer_note_map_from_db(payers)
    pad_matcher = PayerAmountDateMatcher(eobs, payer_note_map=payer_note_map)
    pad_results = pad_matcher.match(
        transactions,
        already_matched_eob_ids=matched_eob_ids,
        already_matched_txn_ids=matched_txn_ids,
    )

    all_results = pn_results + pad_results

    # Persist
    now = datetime.now()
    if all_results:
        rows = [
            {
                "eob": r.eob_id,
                "bank_transaction": r.bank_transaction_id,
                "confidence": r.confidence,
                "match_method": r.match_method,
                "matched_at": now,
            }
            for r in all_results
        ]
        with ReconciliationMatch._meta.database.atomic():
            for i in range(0, len(rows), batch_size):
                ReconciliationMatch.insert_many(
                    rows[i : i + batch_size]
                ).execute()

    logger.info(
        "Matched %d transactions: %d via payment_number, %d via payer_amount_date",
        len(all_results),
        len(pn_results),
        len(pad_results),
    )
    return all_results


def _print_dashboard(results: list[MatchResult], total_insurance: int) -> None:
    """Print a Rich dashboard with matching summary."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    matched = len(results)
    unmatched = total_insurance - matched

    # Summary
    summary = Table(
        title="Reconciliation Dashboard",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    summary.add_column("Category", style="bold")
    summary.add_column("Count", justify="right")
    summary.add_column("%", justify="right")
    summary.add_column("Bar", ratio=1)

    def _row(cat: str, n: int, style: str = "") -> None:
        pct = n / total_insurance * 100 if total_insurance else 0
        bar_len = max(0, int(pct / 2))
        bar = "█" * bar_len
        summary.add_row(cat, f"{n:,}", f"{pct:.1f}%", f"[{style}]{bar}[/]")

    _row("Matched", matched, "green")
    _row("Unmatched", unmatched, "yellow")
    summary.add_row("", "", "", "", style="dim")
    _row("Total insurance txns", total_insurance, "bold")

    console.print()
    console.print(Panel(summary, border_style="blue"))
    console.print()

    # By method
    method_counts: dict[str, int] = {}
    conf_sum: dict[str, float] = {}
    for r in results:
        method_counts[r.match_method] = method_counts.get(r.match_method, 0) + 1
        conf_sum[r.match_method] = conf_sum.get(r.match_method, 0.0) + r.confidence

    method_table = Table(
        title="By Match Method",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    method_table.add_column("Method", style="bold")
    method_table.add_column("Count", justify="right")
    method_table.add_column("Avg Confidence", justify="right")

    for method in sorted(method_counts, key=lambda k: -method_counts[k]):
        n = method_counts[method]
        avg_conf = conf_sum[method] / n if n else 0
        method_table.add_row(method, f"{n:,}", f"{avg_conf:.2f}")

    console.print(Panel(method_table, border_style="blue"))
    console.print()


def main() -> None:
    """CLI entrypoint: run all matchers and persist to reconciliation_matches."""
    import argparse

    from bank_reconciliation.db.database import db
    from bank_reconciliation.db.init_db import init_db
    from bank_reconciliation.db.models import TransactionClassification

    parser = argparse.ArgumentParser(
        description="Match insurance bank transactions to EOBs and persist to DB.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Drop existing matches and re-run all matchers.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Insert batch size for bulk writes (default: 500).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db.connect()
    try:
        init_db()
        results = match_all(overwrite=args.overwrite, batch_size=args.batch_size)

        total_insurance = (
            TransactionClassification.select()
            .where(TransactionClassification.is_insurance == True)  # noqa: E712
            .count()
        )
        _print_dashboard(results, total_insurance)
    finally:
        db.close()


if __name__ == "__main__":
    main()
