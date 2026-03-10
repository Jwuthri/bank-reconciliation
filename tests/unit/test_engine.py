"""Tests for ReconciliationEngine — the real DB-backed implementation.

Uses an in-memory SQLite database so tests are fast and isolated.
"""

from __future__ import annotations

import datetime

import pytest
from peewee import SqliteDatabase

from bank_reconciliation.db.models import (
    EOB,
    BankTransaction,
    BaseModel,
    Payer,
    ReconciliationMatch,
    TransactionClassification,
)
from bank_reconciliation.reconciliation.engine import LiveReconciliationEngine
from bank_reconciliation.reconciliation.models import (
    DashboardPayment,
    MissingEOBTask,
    MissingTransactionTask,
)

MODELS = [Payer, BankTransaction, EOB, TransactionClassification, ReconciliationMatch]

_test_db = SqliteDatabase(":memory:")


@pytest.fixture(autouse=True)
def setup_db():
    """Bind all models to an in-memory DB and create tables for each test."""
    _test_db.bind(MODELS)
    _test_db.connect(reuse_if_open=True)
    _test_db.create_tables(MODELS)
    yield
    _test_db.drop_tables(MODELS)
    if not _test_db.is_closed():
        _test_db.close()


def _dt(day: int = 1, month: int = 9, year: int = 2025) -> datetime.datetime:
    return datetime.datetime(year, month, day)


def _payer(name: str = "Aetna") -> Payer:
    return Payer.create(name=name)


def _bt(amount: int = -10000, note: str | None = None, day: int = 1) -> BankTransaction:
    return BankTransaction.create(amount=amount, note=note, received_at=_dt(day))


def _eob(
    payer: Payer,
    payment_number: str | None = None,
    payment_amount: int = 10000,
    adjusted_amount: int = 10000,
    payment_type: str = "ACH",
    day: int = 1,
) -> EOB:
    return EOB.create(
        payer=payer,
        payment_number=payment_number,
        payment_amount=payment_amount,
        adjusted_amount=adjusted_amount,
        payment_type=payment_type,
        payment_date=_dt(day),
    )


def _classify(bt: BankTransaction, is_insurance: bool, label: str = "test") -> None:
    TransactionClassification.create(
        bank_transaction=bt, is_insurance=is_insurance, label=label, confidence=1.0
    )


def _match(
    eob: EOB,
    bt: BankTransaction,
    confidence: float = 1.0,
    method: str = "payment_number",
) -> None:
    ReconciliationMatch.create(
        eob=eob,
        bank_transaction=bt,
        confidence=confidence,
        match_method=method,
        matched_at=datetime.datetime.now(),
    )


# ──────────────────────────────────────────────────────────────────────
# run_matching
# ──────────────────────────────────────────────────────────────────────


class TestRunMatching:
    def test_classifies_and_matches_hcclaimpmt(self):
        """Full pipeline: classify + payment number match."""
        payer = _payer("UHC")
        eob = _eob(payer, payment_number="736886274", adjusted_amount=28500)
        bt = _bt(
            amount=-28500,
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
        )

        engine = LiveReconciliationEngine()
        stats = engine.run_matching()

        assert stats["classified"] > 0
        assert stats["matched"] >= 1

        match = ReconciliationMatch.get_or_none(
            ReconciliationMatch.eob == eob,
            ReconciliationMatch.bank_transaction == bt,
        )
        assert match is not None
        assert match.confidence == 1.0
        assert match.match_method == "payment_number"

    def test_classifies_and_matches_payer_amount_date(self):
        """Full pipeline: classify + payer amount date match."""
        payer = _payer("MetLife")
        eob = _eob(payer, adjusted_amount=24120, day=5)
        bt = _bt(amount=-24120, note="MetLife", day=7)

        engine = LiveReconciliationEngine()
        stats = engine.run_matching()

        assert stats["matched"] >= 1
        match = ReconciliationMatch.get_or_none(
            ReconciliationMatch.eob == eob,
            ReconciliationMatch.bank_transaction == bt,
        )
        assert match is not None
        assert match.match_method == "payer_amount_date"

    def test_idempotent(self):
        """Running matching twice doesn't duplicate results."""
        payer = _payer("UHC")
        _eob(payer, payment_number="111", adjusted_amount=5000)
        _bt(amount=-5000, note="HCCLAIMPMT TRN*1*111*999\\")

        engine = LiveReconciliationEngine()
        engine.run_matching()
        engine.run_matching()

        assert ReconciliationMatch.select().count() == 1

    def test_noise_transactions_not_matched(self):
        """Noise transactions should be classified but not matched."""
        payer = _payer("UHC")
        _eob(payer, payment_number="222", adjusted_amount=5000)
        _bt(amount=-5000, note="PAYROLL DEPOSIT")

        engine = LiveReconciliationEngine()
        engine.run_matching()

        assert ReconciliationMatch.select().count() == 0


# ──────────────────────────────────────────────────────────────────────
# get_dashboard_payments
# ──────────────────────────────────────────────────────────────────────


class TestGetDashboardPayments:
    def test_matched_pair(self):
        """A matched EOB+transaction shows both statuses as RECEIVED."""
        payer = _payer()
        eob = _eob(payer, payment_number="P001", adjusted_amount=10000, day=5)
        bt = _bt(amount=-10000, note="HCCLAIMPMT TRN*1*P001*X\\", day=5)
        _classify(bt, is_insurance=True)
        _match(eob, bt)

        engine = LiveReconciliationEngine()
        result = engine.get_dashboard_payments(page=0, page_size=20)

        assert result.total_count >= 1
        matched = [p for p in result.items if p.eob_id == eob.id]
        assert len(matched) == 1
        p = matched[0]
        assert p.bank_transaction_status == "RECEIVED"
        assert p.eob_status == "RECEIVED"
        assert p.transaction_id == bt.id
        assert p.adjusted_amount == 10000

    def test_unmatched_eob(self):
        """An EOB with no match shows transaction status AWAITING."""
        payer = _payer()
        eob = _eob(payer, payment_number="P002", adjusted_amount=20000, day=3)

        engine = LiveReconciliationEngine()
        result = engine.get_dashboard_payments(page=0, page_size=50)

        unmatched = [p for p in result.items if p.eob_id == eob.id]
        assert len(unmatched) == 1
        p = unmatched[0]
        assert p.bank_transaction_status == "AWAITING"
        assert p.eob_status == "RECEIVED"
        assert p.transaction_id is None

    def test_unmatched_insurance_transaction(self):
        """An insurance transaction with no match shows EOB status AWAITING."""
        bt = _bt(amount=-15000, note="HCCLAIMPMT something", day=10)
        _classify(bt, is_insurance=True)

        engine = LiveReconciliationEngine()
        result = engine.get_dashboard_payments(page=0, page_size=50)

        unmatched = [p for p in result.items if p.transaction_id == bt.id]
        assert len(unmatched) == 1
        p = unmatched[0]
        assert p.bank_transaction_status == "RECEIVED"
        assert p.eob_status == "AWAITING"
        assert p.eob_id is None

    def test_noise_transactions_excluded(self):
        """Non-insurance transactions don't appear in dashboard payments."""
        bt = _bt(amount=-5000, note="PAYROLL DEPOSIT", day=10)
        _classify(bt, is_insurance=False)

        engine = LiveReconciliationEngine()
        result = engine.get_dashboard_payments(page=0, page_size=50)

        txn_ids = [p.transaction_id for p in result.items]
        assert bt.id not in txn_ids

    def test_pagination(self):
        """Pagination returns correct slices and metadata."""
        payer = _payer()
        for i in range(5):
            _eob(payer, payment_number=f"PG{i}", adjusted_amount=1000 * (i + 1), day=i + 1)

        engine = LiveReconciliationEngine()
        page0 = engine.get_dashboard_payments(page=0, page_size=2)
        page1 = engine.get_dashboard_payments(page=1, page_size=2)

        assert page0.page == 0
        assert page0.page_size == 2
        assert len(page0.items) == 2
        assert page0.total_count == 5
        assert page0.has_next is True

        assert page1.page == 1
        assert len(page1.items) == 2
        assert page1.has_prev is True

    def test_ordered_newest_first(self):
        """Results are ordered by date descending."""
        payer = _payer()
        _eob(payer, payment_number="OLD", adjusted_amount=1000, day=1)
        _eob(payer, payment_number="NEW", adjusted_amount=2000, day=15)

        engine = LiveReconciliationEngine()
        result = engine.get_dashboard_payments(page=0, page_size=10)

        dates = [p.date for p in result.items]
        assert dates == sorted(dates, reverse=True)

    def test_zero_dollar_non_payment_excluded_from_unmatched_eobs(self):
        """NON_PAYMENT with adjusted_amount=0 should not appear as unmatched EOB."""
        payer = _payer()
        eob = _eob(
            payer,
            payment_number="NP001",
            payment_amount=0,
            adjusted_amount=0,
            payment_type="NON_PAYMENT",
            day=5,
        )

        engine = LiveReconciliationEngine()
        result = engine.get_dashboard_payments(page=0, page_size=50)

        eob_ids = [p.eob_id for p in result.items]
        assert eob.id not in eob_ids


# ──────────────────────────────────────────────────────────────────────
# get_missing_bank_transactions
# ──────────────────────────────────────────────────────────────────────


class TestGetMissingBankTransactions:
    def test_unmatched_eob_appears(self):
        """An EOB with no match appears in missing transactions."""
        payer = _payer("Delta")
        eob = _eob(payer, payment_number="M001", adjusted_amount=30000, day=5)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_bank_transactions(page=0, page_size=20)

        eob_ids = [t.eob_id for t in result.items]
        assert eob.id in eob_ids

        task = next(t for t in result.items if t.eob_id == eob.id)
        assert task.payer_name == "Delta"
        assert task.payment_number == "M001"
        assert task.adjusted_amount == 30000

    def test_matched_eob_excluded(self):
        """A matched EOB does NOT appear in missing transactions."""
        payer = _payer()
        eob = _eob(payer, payment_number="M002", adjusted_amount=5000, day=5)
        bt = _bt(amount=-5000, day=5)
        _classify(bt, is_insurance=True)
        _match(eob, bt)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_bank_transactions(page=0, page_size=20)

        eob_ids = [t.eob_id for t in result.items]
        assert eob.id not in eob_ids

    def test_zero_dollar_non_payment_excluded(self):
        """NON_PAYMENT with adjusted_amount=0 excluded from missing transactions."""
        payer = _payer()
        eob = _eob(
            payer,
            payment_number="NP002",
            payment_amount=0,
            adjusted_amount=0,
            payment_type="NON_PAYMENT",
            day=5,
        )

        engine = LiveReconciliationEngine()
        result = engine.get_missing_bank_transactions(page=0, page_size=20)

        eob_ids = [t.eob_id for t in result.items]
        assert eob.id not in eob_ids

    def test_ordered_newest_first(self):
        payer = _payer()
        _eob(payer, payment_number="OLD", adjusted_amount=1000, day=1)
        _eob(payer, payment_number="NEW", adjusted_amount=2000, day=20)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_bank_transactions(page=0, page_size=10)

        assert result.items[0].payment_number == "NEW"


# ──────────────────────────────────────────────────────────────────────
# get_missing_payment_eobs
# ──────────────────────────────────────────────────────────────────────


class TestGetMissingPaymentEobs:
    def test_unmatched_insurance_txn_appears(self):
        """An insurance transaction with no match appears in missing EOBs."""
        bt = _bt(amount=-25000, note="HCCLAIMPMT TRN*1*999*X\\", day=8)
        _classify(bt, is_insurance=True)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_payment_eobs(page=0, page_size=20)

        txn_ids = [t.transaction_id for t in result.items]
        assert bt.id in txn_ids

        task = next(t for t in result.items if t.transaction_id == bt.id)
        assert task.amount == -25000

    def test_matched_insurance_txn_excluded(self):
        """A matched insurance transaction does NOT appear in missing EOBs."""
        payer = _payer()
        eob = _eob(payer, payment_number="E001", adjusted_amount=5000, day=5)
        bt = _bt(amount=-5000, note="HCCLAIMPMT TRN*1*E001*X\\", day=5)
        _classify(bt, is_insurance=True)
        _match(eob, bt)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_payment_eobs(page=0, page_size=20)

        txn_ids = [t.transaction_id for t in result.items]
        assert bt.id not in txn_ids

    def test_noise_txn_excluded(self):
        """Non-insurance transactions don't appear in missing EOBs."""
        bt = _bt(amount=-5000, note="PAYROLL", day=5)
        _classify(bt, is_insurance=False)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_payment_eobs(page=0, page_size=20)

        txn_ids = [t.transaction_id for t in result.items]
        assert bt.id not in txn_ids

    def test_ordered_newest_first(self):
        bt_old = _bt(amount=-1000, note="HCCLAIMPMT old", day=1)
        bt_new = _bt(amount=-2000, note="HCCLAIMPMT new", day=20)
        _classify(bt_old, is_insurance=True)
        _classify(bt_new, is_insurance=True)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_payment_eobs(page=0, page_size=10)

        assert result.items[0].transaction_id == bt_new.id

    def test_extracts_payment_number_from_note(self):
        """Missing EOB task should extract payment number from TRN if present."""
        bt = _bt(amount=-5000, note="HCCLAIMPMT TRN*1*ABC123*X\\", day=5)
        _classify(bt, is_insurance=True)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_payment_eobs(page=0, page_size=20)

        task = next(t for t in result.items if t.transaction_id == bt.id)
        assert task.payment_number == "ABC123"

    def test_infers_payer_name_from_note(self):
        """Missing EOB task should infer payer name from note if possible."""
        bt = _bt(amount=-5000, note="MetLife", day=5)
        _classify(bt, is_insurance=True)

        engine = LiveReconciliationEngine()
        result = engine.get_missing_payment_eobs(page=0, page_size=20)

        task = next(t for t in result.items if t.transaction_id == bt.id)
        assert task.payer_name == "MetLife"
