import random
from datetime import datetime, timedelta

from .base import ReconciliationEngine
from .models import (
    DashboardPayment,
    MissingEOBTask,
    MissingTransactionTask,
    PaginatedResult,
)

PAYER_NAMES = ["Aetna", "Cigna", "UHC", "BCBS", "MetLife", "Delta Dental"]
PAYMENT_TYPES = ["ACH", "CHECK", "VCC"]


class DummyReconciliationEngine(ReconciliationEngine):
    """Dummy engine that generates fake data for testing the UI."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def _random_date(self, rng: random.Random) -> datetime:
        return datetime.now() - timedelta(days=rng.randint(0, 30))

    def get_dashboard_payments(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[DashboardPayment]:
        rng = random.Random(self.seed)
        all_payments = []

        for i in range(1, 81):
            date = self._random_date(rng)
            kind = rng.choices(
                ["matched", "unmatched_eob", "unmatched_txn"], weights=[60, 20, 20]
            )[0]

            base_amount = rng.randint(10000, 500000)
            adjustment = rng.choice([0, 0, 0, rng.randint(-500, 500)])

            if kind == "matched":
                payment = DashboardPayment(
                    eob_id=i,
                    transaction_id=i,
                    payer_name=rng.choice(PAYER_NAMES),
                    payment_number=f"P{i:04d}",
                    payment_amount=base_amount,
                    adjusted_amount=base_amount + adjustment,
                    date=date,
                    bank_transaction_status="RECEIVED",
                    eob_status="RECEIVED",
                )
            elif kind == "unmatched_eob":
                payment = DashboardPayment(
                    eob_id=i,
                    payer_name=rng.choice(PAYER_NAMES),
                    payment_number=f"P{i:04d}",
                    payment_amount=base_amount,
                    adjusted_amount=base_amount + adjustment,
                    date=date,
                    bank_transaction_status="AWAITING",
                    eob_status="RECEIVED",
                )
            else:
                payment = DashboardPayment(
                    transaction_id=i,
                    adjusted_amount=base_amount,
                    date=date,
                    bank_transaction_status="RECEIVED",
                    eob_status="AWAITING",
                )

            all_payments.append(payment)

        total_count = len(all_payments)
        start_idx = page * page_size
        page_items = all_payments[start_idx : start_idx + page_size]

        return PaginatedResult(
            items=page_items,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    def get_missing_bank_transactions(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[MissingTransactionTask]:
        rng = random.Random(self.seed)
        all_tasks = []

        for i in range(1, 31):
            task = MissingTransactionTask(
                eob_id=i,
                payment_number=f"P{i:04d}",
                payer_name=rng.choice(PAYER_NAMES),
                payment_type=rng.choice(PAYMENT_TYPES),
                adjusted_amount=rng.randint(10000, 500000),
            )
            all_tasks.append(task)

        total_count = len(all_tasks)
        start_idx = page * page_size
        page_items = all_tasks[start_idx : start_idx + page_size]

        return PaginatedResult(
            items=page_items,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    def get_missing_payment_eobs(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[MissingEOBTask]:
        rng = random.Random(self.seed)
        all_tasks = []

        for i in range(1, 31):
            has_info = i <= 20

            task = MissingEOBTask(
                transaction_id=i,
                payer_name=rng.choice(PAYER_NAMES) if has_info else None,
                payment_number=f"P{i:04d}" if has_info else None,
                amount=rng.randint(10000, 500000),
                received_at=self._random_date(rng),
            )
            all_tasks.append(task)

        total_count = len(all_tasks)
        start_idx = page * page_size
        page_items = all_tasks[start_idx : start_idx + page_size]

        return PaginatedResult(
            items=page_items,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )
