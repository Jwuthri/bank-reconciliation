"""Real DB-backed ReconciliationEngine.

Orchestrates the classifier and matchers, persists results to
``reconciliation_matches``, and serves paginated queries for the
dashboard and CLI.
"""

from __future__ import annotations

import datetime
import logging
from typing import Literal

from peewee import JOIN, fn

from bank_reconciliation.db.models import (
    EOB,
    BankTransaction,
    Payer,
    ReconciliationMatch,
    TransactionClassification,
)
from bank_reconciliation.reconciliation.classifier import classify_all
from bank_reconciliation.reconciliation.normalize import normalize_note
from bank_reconciliation.reconciliation.matchers import (
    MatchResult,
    Matcher,
    PayerAmountDateMatcher,
    PaymentNumberMatcher,
    build_payer_note_map_from_db,
    extract_trn_payment_number,
)

from .base import ReconciliationEngine
from .models import (
    DashboardPayment,
    MissingEOBTask,
    MissingTransactionTask,
    PaginatedResult,
    ReconciliationStats,
)

logger = logging.getLogger(__name__)


def _infer_payer_name(note: str | None) -> str | None:
    """Infer display name for payer from bank transaction note."""
    from bank_reconciliation.reconciliation.payer_registry import (
        HCCLAIMPMT_PAYER_CODES,
        NOTE_PATTERN_TO_DISPLAY_NAME,
    )

    normalized = normalize_note(note)
    if not normalized:
        return None
    for pattern, name in NOTE_PATTERN_TO_DISPLAY_NAME.items():
        if pattern.upper() in normalized.upper():
            return name
    if "HCCLAIMPMT" in normalized.upper():
        for code, payer in HCCLAIMPMT_PAYER_CODES.items():
            if code.upper() in normalized.upper():
                return payer
        return "HCCLAIMPMT"
    return None


class LiveReconciliationEngine(ReconciliationEngine):
    """Production engine backed by SQLite via Peewee."""

    def run_matching(
        self,
        *,
        use_llm: bool = True,
        mode: Literal["precision", "recall"] = "precision",
        overwrite: bool = False,
    ) -> dict[str, int]:
        """Run the full classify → match pipeline and persist results.

        Stage 1: Classify all bank transactions as insurance or not.
        Stage 2: Match insurance transactions to EOBs.

        Returns summary stats: {classified, matched, skipped_existing}.
        """
        stats: dict[str, int] = {}

        # Stage 1: classify
        counts = classify_all(use_llm=use_llm, mode=mode, overwrite=overwrite)
        stats["classified"] = sum(counts.values())

        # Stage 2: match
        insurance_txns = list(
            BankTransaction.select()
            .join(TransactionClassification)
            .where(TransactionClassification.is_insurance == True)  # noqa: E712
        )

        eobs = list(EOB.select())

        already_matched_eob_ids: set[int] = {
            row.eob_id for row in ReconciliationMatch.select(ReconciliationMatch.eob)
        }
        already_matched_txn_ids: set[int] = {
            row.bank_transaction_id
            for row in ReconciliationMatch.select(
                ReconciliationMatch.bank_transaction
            )
            if row.bank_transaction_id is not None
        }

        # Run matchers in order; each matcher sees results from previous ones
        payer_note_map = build_payer_note_map_from_db(list(Payer.select()))
        matchers: list[Matcher] = [
            PaymentNumberMatcher(eobs),
            PayerAmountDateMatcher(
                eobs, payer_note_map=payer_note_map, date_window_days=5
            ),
        ]

        all_results: list[MatchResult] = []
        for matcher in matchers:
            results = matcher.match(
                insurance_txns,
                already_matched_eob_ids=already_matched_eob_ids,
                already_matched_txn_ids=already_matched_txn_ids,
            )
            for mr in results:
                already_matched_eob_ids.add(mr.eob_id)
                already_matched_txn_ids.add(mr.bank_transaction_id)
            all_results.extend(results)
        now = datetime.datetime.now()

        if all_results:
            rows = [
                {
                    "eob": mr.eob_id,
                    "bank_transaction": mr.bank_transaction_id,
                    "confidence": mr.confidence,
                    "match_method": mr.match_method,
                    "matched_at": now,
                }
                for mr in all_results
            ]
            with ReconciliationMatch._meta.database.atomic():
                for i in range(0, len(rows), 500):
                    ReconciliationMatch.insert_many(rows[i : i + 500]).execute()

        stats["matched"] = len(all_results)
        stats["skipped_existing"] = len(
            {row.eob_id for row in ReconciliationMatch.select(ReconciliationMatch.eob)}
        ) - len(all_results)

        method_counts: dict[str, int] = {}
        for mr in all_results:
            method_counts[mr.match_method] = method_counts.get(mr.match_method, 0) + 1
        logger.info(
            "Matching complete: %d new matches (%d payment_number, %d payer_amount_date)",
            len(all_results),
            method_counts.get("payment_number", 0),
            method_counts.get("payer_amount_date", 0),
        )
        return stats

    # ──────────────────────────────────────────────────────────────────
    # Dashboard queries
    # ──────────────────────────────────────────────────────────────────

    def get_dashboard_payments(
        self,
        page: int = 0,
        page_size: int = 20,
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> PaginatedResult[DashboardPayment]:
        matched_eob_ids_sq = ReconciliationMatch.select(ReconciliationMatch.eob)
        matched_txn_ids_sq = ReconciliationMatch.select(
            ReconciliationMatch.bank_transaction
        )

        # Load all items (no pagination at DB level for sort support)
        items: list[DashboardPayment] = []

        # --- Category 1: Matched pairs ---
        matched_query = (
            ReconciliationMatch.select(
                ReconciliationMatch, EOB, BankTransaction, Payer,
            )
            .join(EOB, on=(ReconciliationMatch.eob == EOB.id))
            .join(Payer, on=(EOB.payer == Payer.id))
            .switch(ReconciliationMatch)
            .join(
                BankTransaction,
                on=(ReconciliationMatch.bank_transaction == BankTransaction.id),
            )
        )
        for row in matched_query:
            eob = row.eob
            bt = row.bank_transaction
            items.append(
                DashboardPayment(
                    eob_id=eob.id,
                    transaction_id=bt.id,
                    payer_name=eob.payer.name,
                    payment_number=eob.payment_number,
                    payment_amount=eob.payment_amount,
                    adjusted_amount=eob.adjusted_amount,
                    date=eob.payment_date,
                    bank_transaction_status="RECEIVED",
                    eob_status="RECEIVED",
                    match_method=row.match_method,
                )
            )

        # --- Category 2: Unmatched EOBs ---
        eob_query = (
            EOB.select(EOB, Payer)
            .join(Payer, on=(EOB.payer == Payer.id))
            .where(EOB.id.not_in(matched_eob_ids_sq))
            .where(
                ~(
                    (EOB.payment_type == "NON_PAYMENT")
                    & (EOB.adjusted_amount == 0)
                )
            )
        )
        for eob in eob_query:
            items.append(
                DashboardPayment(
                    eob_id=eob.id,
                    transaction_id=None,
                    payer_name=eob.payer.name,
                    payment_number=eob.payment_number,
                    payment_amount=eob.payment_amount,
                    adjusted_amount=eob.adjusted_amount,
                    date=eob.payment_date,
                    bank_transaction_status="AWAITING",
                    eob_status="RECEIVED",
                )
            )

        # --- Category 3: Unmatched insurance transactions ---
        txn_query = (
            BankTransaction.select(BankTransaction, TransactionClassification)
            .join(TransactionClassification)
            .where(TransactionClassification.is_insurance == True)  # noqa: E712
            .where(BankTransaction.id.not_in(matched_txn_ids_sq))
        )
        for bt in txn_query:
            items.append(
                DashboardPayment(
                    eob_id=None,
                    transaction_id=bt.id,
                    payer_name=_infer_payer_name(bt.note),
                    payment_number=extract_trn_payment_number(bt.note),
                    payment_amount=None,
                    adjusted_amount=abs(bt.amount),
                    date=bt.received_at,
                    bank_transaction_status="RECEIVED",
                    eob_status="AWAITING",
                )
            )

        # Sort
        reverse = sort_order.lower() == "desc"

        def _sort_key(p: DashboardPayment):
            if sort_by == "date":
                return p.date or datetime.datetime.min
            if sort_by == "payer":
                return (p.payer_name or "").lower()
            if sort_by == "payment_number":
                return (p.payment_number or "").lower()
            if sort_by == "amount":
                return p.adjusted_amount or 0
            if sort_by == "method":
                return (p.match_method or "").lower()
            return p.date or datetime.datetime.min

        items.sort(key=_sort_key, reverse=reverse)

        # Paginate
        total_count = len(items)
        start = page * page_size
        items = items[start : start + page_size]

        return PaginatedResult(
            items=items,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    def get_missing_bank_transactions(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[MissingTransactionTask]:
        matched_eob_ids_sq = ReconciliationMatch.select(ReconciliationMatch.eob)

        query = (
            EOB.select(EOB, Payer)
            .join(Payer, on=(EOB.payer == Payer.id))
            .where(EOB.id.not_in(matched_eob_ids_sq))
            .where(
                ~(
                    (EOB.payment_type == "NON_PAYMENT") & (EOB.adjusted_amount == 0)
                )
            )
            .order_by(EOB.payment_date.desc())
        )

        total_count = query.count()

        page_rows = query.offset(page * page_size).limit(page_size)

        items = [
            MissingTransactionTask(
                eob_id=eob.id,
                payment_number=eob.payment_number or "",
                payer_name=eob.payer.name,
                payment_type=eob.payment_type,
                adjusted_amount=eob.adjusted_amount,
            )
            for eob in page_rows
        ]

        return PaginatedResult(
            items=items,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    def get_missing_payment_eobs(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[MissingEOBTask]:
        matched_txn_ids_sq = ReconciliationMatch.select(
            ReconciliationMatch.bank_transaction
        )

        query = (
            BankTransaction.select(BankTransaction, TransactionClassification)
            .join(TransactionClassification)
            .where(TransactionClassification.is_insurance == True)  # noqa: E712
            .where(BankTransaction.id.not_in(matched_txn_ids_sq))
            .order_by(BankTransaction.received_at.desc())
        )

        total_count = query.count()

        page_rows = query.offset(page * page_size).limit(page_size)

        items = [
            MissingEOBTask(
                transaction_id=bt.id,
                payer_name=_infer_payer_name(bt.note),
                payment_number=extract_trn_payment_number(bt.note),
                amount=bt.amount,
                received_at=bt.received_at,
            )
            for bt in page_rows
        ]

        return PaginatedResult(
            items=items,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    def manual_reconcile(self, eob_id: int, transaction_id: int) -> int:
        """Create a manual match between an EOB and a bank transaction.

        Returns the created ReconciliationMatch id.
        Raises ValueError if IDs are invalid or already matched.
        """
        eob = EOB.get_or_none(EOB.id == eob_id)
        if eob is None:
            raise ValueError(f"EOB {eob_id} not found")

        bt = BankTransaction.get_or_none(BankTransaction.id == transaction_id)
        if bt is None:
            raise ValueError(f"Bank transaction {transaction_id} not found")

        existing_eob_match = ReconciliationMatch.get_or_none(
            ReconciliationMatch.eob == eob_id
        )
        if existing_eob_match is not None:
            raise ValueError(f"EOB {eob_id} is already matched")

        existing_txn_matches = list(
            ReconciliationMatch.select().where(
                ReconciliationMatch.bank_transaction == transaction_id
            )
        )
        if existing_txn_matches:
            raise ValueError(f"Transaction {transaction_id} is already matched")

        # Transaction must be classified as insurance
        tc = TransactionClassification.get_or_none(
            TransactionClassification.bank_transaction == transaction_id
        )
        if tc is None or not tc.is_insurance:
            raise ValueError(
                f"Transaction {transaction_id} is not classified as insurance"
            )

        match = ReconciliationMatch.create(
            eob=eob,
            bank_transaction=bt,
            confidence=1.0,
            match_method="manual",
            matched_at=datetime.datetime.now(),
        )
        return match.id

    def dismiss_item(
        self, *, eob_id: int | None = None, transaction_id: int | None = None
    ) -> int:
        """Mark an unmatched EOB or transaction as dismissed (not reconcilable).

        Exactly one of eob_id or transaction_id must be provided.
        Returns the created ReconciliationMatch id for EOB dismissals, or 0 for
        transaction dismissals (which update classification).
        Raises ValueError if invalid.
        """
        if (eob_id is None) == (transaction_id is None):
            raise ValueError("Exactly one of eob_id or transaction_id must be provided")

        if eob_id is not None:
            eob = EOB.get_or_none(EOB.id == eob_id)
            if eob is None:
                raise ValueError(f"EOB {eob_id} not found")
            existing = ReconciliationMatch.get_or_none(ReconciliationMatch.eob == eob_id)
            if existing is not None:
                raise ValueError(f"EOB {eob_id} is already matched")
            match = ReconciliationMatch.create(
                eob=eob,
                bank_transaction=None,
                confidence=1.0,
                match_method="manual_dismiss",
                matched_at=datetime.datetime.now(),
            )
            return match.id

        # transaction_id provided: mark as not insurance so it drops out of reconciliation
        bt = BankTransaction.get_or_none(BankTransaction.id == transaction_id)
        if bt is None:
            raise ValueError(f"Bank transaction {transaction_id} not found")
        existing = list(
            ReconciliationMatch.select().where(
                ReconciliationMatch.bank_transaction == transaction_id
            )
        )
        if existing:
            raise ValueError(f"Transaction {transaction_id} is already matched")

        tc, _ = TransactionClassification.get_or_create(
            bank_transaction=bt,
            defaults={
                "is_insurance": False,
                "label": "manual_dismissed",
                "confidence": 1.0,
            },
        )
        if tc.is_insurance:
            tc.is_insurance = False
            tc.label = "manual_dismissed"
            tc.save()
        return 0

    def get_stats(self) -> ReconciliationStats:
        """Return aggregate statistics for classification and reconciliation."""
        total_transactions = BankTransaction.select().count()
        classified = TransactionClassification.select()
        insurance_count = classified.where(
            TransactionClassification.is_insurance == True  # noqa: E712
        ).count()
        not_insurance_count = classified.where(
            TransactionClassification.is_insurance == False  # noqa: E712
        ).count()
        classified_count = insurance_count + not_insurance_count
        unknown_count = total_transactions - classified_count

        total_eobs = EOB.select().count()
        matched_count = ReconciliationMatch.select().count()
        matched_eob_ids_sq = ReconciliationMatch.select(ReconciliationMatch.eob)
        unmatched_eob_base = (
            EOB.select()
            .where(EOB.id.not_in(matched_eob_ids_sq))
            .where(
                ~(
                    (EOB.payment_type == "NON_PAYMENT") & (EOB.adjusted_amount == 0)
                )
            )
        )
        unmatched_eob_count = unmatched_eob_base.count()

        matched_txn_ids_sq = ReconciliationMatch.select(
            ReconciliationMatch.bank_transaction
        )
        unmatched_txn_base = (
            BankTransaction.select()
            .join(TransactionClassification)
            .where(TransactionClassification.is_insurance == True)  # noqa: E712
            .where(BankTransaction.id.not_in(matched_txn_ids_sq))
        )
        unmatched_txn_count = unmatched_txn_base.count()

        match_by_method: dict[str, int] = {}
        for row in ReconciliationMatch.select(ReconciliationMatch.match_method).tuples():
            method = row[0]
            match_by_method[method] = match_by_method.get(method, 0) + 1

        manual_match_count = match_by_method.get("manual", 0) + match_by_method.get(
            "manual_dismiss", 0
        )
        auto_match_count = matched_count - manual_match_count

        return ReconciliationStats(
            total_transactions=total_transactions,
            insurance_count=insurance_count,
            not_insurance_count=not_insurance_count,
            unknown_count=max(0, unknown_count),
            total_eobs=total_eobs,
            matched_count=matched_count,
            unmatched_eob_count=unmatched_eob_count,
            unmatched_txn_count=unmatched_txn_count,
            manual_match_count=manual_match_count,
            auto_match_count=auto_match_count,
            match_by_method=match_by_method,
        )
