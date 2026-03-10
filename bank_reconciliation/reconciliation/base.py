from .models import (
    DashboardPayment,
    MissingEOBTask,
    MissingTransactionTask,
    PaginatedResult,
    ReconciliationStats,
)


class ReconciliationEngine:
    def run_matching(self, **kwargs) -> dict[str, int]:
        """Run the classify → match pipeline and persist results.

        Default no-op for engines that do not support matching.
        Returns empty stats dict.
        """
        return {}

    def get_dashboard_payments(
        self,
        page: int = 0,
        page_size: int = 20,
        sort_by: str = "date",
        sort_order: str = "desc",
    ) -> PaginatedResult[DashboardPayment]:
        """Return paginated join of EOBs and bank transactions for practice dashboard.

        This returns a combined view of EOBs and bank transactions with status flags
        indicating what's missing: transactions without matching EOBs, or EOBs without
        matching bank transactions.

        Results are ordered by newest first.

        Args:
            page: Zero-indexed page number
            page_size: Number of items per page
        Returns:
            PaginatedResult containing page items and metadata
        """
        raise NotImplementedError

    def get_missing_bank_transactions(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[MissingTransactionTask]:
        """Return paginated list of EOBs missing bank transactions.

        Results are ordered by newest first.

        Args:
            page: Zero-indexed page number
            page_size: Number of items per page
        Returns:
            PaginatedResult containing page items and metadata
        """
        raise NotImplementedError

    def get_missing_payment_eobs(
        self, page: int = 0, page_size: int = 20
    ) -> PaginatedResult[MissingEOBTask]:
        """Return paginated list of transactions missing EOBs.

        Results are ordered by newest first.

        Args:
            page: Zero-indexed page number
            page_size: Number of items per page
        Returns:
            PaginatedResult containing page items and metadata
        """
        raise NotImplementedError

    def manual_reconcile(self, eob_id: int, transaction_id: int) -> int:
        """Create a manual match between an EOB and a bank transaction.

        Returns the created ReconciliationMatch id.
        Raises ValueError if IDs are invalid or already matched.
        """
        raise NotImplementedError

    def dismiss_item(
        self, *, eob_id: int | None = None, transaction_id: int | None = None
    ) -> int:
        """Mark an unmatched EOB or transaction as dismissed (not reconcilable).

        Exactly one of eob_id or transaction_id must be provided.
        Returns the created ReconciliationMatch id.
        Raises ValueError if invalid.
        """
        raise NotImplementedError

    def get_stats(self) -> ReconciliationStats:
        """Return aggregate statistics for classification and reconciliation."""
        raise NotImplementedError
