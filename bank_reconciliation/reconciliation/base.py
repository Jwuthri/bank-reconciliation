from .models import (
    DashboardPayment,
    MissingEOBTask,
    MissingTransactionTask,
    PaginatedResult,
)


class ReconciliationEngine:
    def run_matching(self, **kwargs) -> dict[str, int]:
        """Run the classify → match pipeline and persist results.

        Default no-op for engines that do not support matching.
        Returns empty stats dict.
        """
        return {}

    def get_dashboard_payments(
        self, page: int = 0, page_size: int = 20
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
