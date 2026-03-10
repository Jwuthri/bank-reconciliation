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
from bank_reconciliation.reconciliation.matchers import (
    PayerAmountDateMatcher,
    PaymentNumberMatcher,
    extract_trn_payment_number,
)

from .base import ReconciliationEngine
from .models import (
    DashboardPayment,
    MissingEOBTask,
    MissingTransactionTask,
    PaginatedResult,
)

logger = logging.getLogger(__name__)

_PAYER_PATTERNS: list[tuple[str, str]] = [
    ("MetLife", "MetLife"),
    ("CALIFORNIA DENTA", "California Dental"),
    ("Guardian Life", "Guardian"),
]

_HCCLAIMPMT_PAYER_CODES: dict[str, str | None] = {
    "UHCDComm": "UnitedHealthcare",
    "PAY PLUS": "Anthem/Cigna",
    "DELTADENTALCA": "Delta Dental",
    "DELTADNTLINS": "Delta Dental",
    "DELTADIC-FEDVIP": "Delta Dental",
    "HUMANA": "Humana",
    "GEHA": "GEHA",
    "CIGNA": "Cigna",
    "ANTHEM": "Anthem",
    "UMR": "UMR",
    "DDPAR": "Delta Dental",
    "DENTEGRA": "Ameritas/Dentegra",
    "HNB - ECHO": None,
    "PNC-ECHO": None,
}


def _infer_payer_name(note: str | None) -> str | None:
    if not note:
        return None
    for pattern, name in _PAYER_PATTERNS:
        if pattern in note:
            return name
    if "HCCLAIMPMT" in note:
        for code, payer in _HCCLAIMPMT_PAYER_CODES.items():
            if code in note:
                return payer
        return "HCCLAIMPMT"
    return None


class LiveReconciliationEngine(ReconciliationEngine):
    """Production engine backed by SQLite via Peewee."""

    def run_matching(
        self,
        *,
        use_llm: bool = False,
        mode: Literal["precision", "recall"] = "precision",
    ) -> dict[str, int]:
        """Run the full classify → match pipeline and persist results.

        Returns summary stats: {classified, matched, skipped_existing}.
        """
        stats: dict[str, int] = {}

        # Stage 1: classify
        counts = classify_all(use_llm=use_llm, mode=mode)
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

        # Matcher 1: payment number
        pn_matcher = PaymentNumberMatcher(eobs)
        pn_results = pn_matcher.match(
            insurance_txns,
            already_matched_eob_ids=already_matched_eob_ids,
            already_matched_txn_ids=already_matched_txn_ids,
        )

        for mr in pn_results:
            already_matched_eob_ids.add(mr.eob_id)
            already_matched_txn_ids.add(mr.bank_transaction_id)

        # Matcher 2: payer + amount + date
        pad_matcher = PayerAmountDateMatcher(
            eobs, payer_note_map=None, date_window_days=5
        )
        pad_results = pad_matcher.match(
            insurance_txns,
            already_matched_eob_ids=already_matched_eob_ids,
            already_matched_txn_ids=already_matched_txn_ids,
        )

        all_results = pn_results + pad_results
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

        logger.info(
            "Matching complete: %d new matches (%d payment_number, %d payer_amount_date)",
            len(all_results),
            len(pn_results),
            len(pad_results),
        )
        return stats

    # ──────────────────────────────────────────────────────────────────
    # Dashboard queries
    # ──────────────────────────────────────────────────────────────────

    def get_dashboard_payments(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[DashboardPayment]:
        matched_eob_ids_sq = ReconciliationMatch.select(ReconciliationMatch.eob)
        matched_txn_ids_sq = ReconciliationMatch.select(
            ReconciliationMatch.bank_transaction
        )

        # Count each category via DB
        matched_count = ReconciliationMatch.select().count()

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

        unmatched_txn_base = (
            BankTransaction.select()
            .join(TransactionClassification)
            .where(TransactionClassification.is_insurance == True)  # noqa: E712
            .where(BankTransaction.id.not_in(matched_txn_ids_sq))
        )
        unmatched_txn_count = unmatched_txn_base.count()

        total_count = matched_count + unmatched_eob_count + unmatched_txn_count

        # Walk through the three categories in order (matched, unmatched EOBs,
        # unmatched txns) and only fetch the rows that fall on the requested page.
        offset = page * page_size
        remaining = page_size
        items: list[DashboardPayment] = []

        # --- Category 1: Matched pairs (sorted by EOB payment_date DESC) ---
        if offset < matched_count and remaining > 0:
            skip = offset
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
                .order_by(EOB.payment_date.desc())
                .offset(skip)
                .limit(remaining)
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
                    )
                )
            remaining -= len(items)

        # --- Category 2: Unmatched EOBs ---
        cat2_start = matched_count
        if offset < cat2_start + unmatched_eob_count and remaining > 0:
            skip = max(0, offset - cat2_start)
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
                .order_by(EOB.payment_date.desc())
                .offset(skip)
                .limit(remaining)
            )
            before = len(items)
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
            remaining -= len(items) - before

        # --- Category 3: Unmatched insurance transactions ---
        cat3_start = matched_count + unmatched_eob_count
        if offset < cat3_start + unmatched_txn_count and remaining > 0:
            skip = max(0, offset - cat3_start)
            txn_query = (
                BankTransaction.select(BankTransaction, TransactionClassification)
                .join(TransactionClassification)
                .where(TransactionClassification.is_insurance == True)  # noqa: E712
                .where(BankTransaction.id.not_in(matched_txn_ids_sq))
                .order_by(BankTransaction.received_at.desc())
                .offset(skip)
                .limit(remaining)
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
