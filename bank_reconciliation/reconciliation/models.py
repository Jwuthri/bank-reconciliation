from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class DashboardPayment(BaseModel):
    """Dashboard's perspective of a payment: a matched pair, unmatched EOB,
    or unmatched bank transaction. Each row in the Payments view maps to one
    of these. Fields from the missing side are None."""

    eob_id: int | None = Field(None, description="EOB ID (present when EOB exists).")
    transaction_id: int | None = Field(
        None, description="Bank transaction ID (present when transaction exists)."
    )
    payer_name: str | None = Field(
        None, description="Payer name from EOB or inferred from transaction note."
    )
    payment_number: str | None = Field(
        None, description="Payment reference number from EOB."
    )
    payment_amount: int | None = Field(
        None, description="Base payment amount in cents from EOB."
    )
    adjusted_amount: int | None = Field(
        None,
        description="payment_amount + adjustments in cents, or bank txn amount.",
    )
    date: datetime = Field(
        ..., description="EOB payment_date or bank transaction received_at."
    )
    bank_transaction_status: Literal["AWAITING", "RECEIVED"] = Field(
        ..., description="Whether a bank transaction exists for this item."
    )
    eob_status: Literal["AWAITING", "RECEIVED"] = Field(
        ..., description="Whether an EOB exists for this item."
    )
    match_method: str | None = Field(
        None,
        description="How the match was made: payment_number, payer_amount_date, manual, manual_dismiss, or None if unmatched.",
    )


class MissingTransactionTask(BaseModel):
    """Dashboard inbox task: an EOB with no matching bank transaction.
    Surfaced so the practice can manually reconcile the payment."""

    eob_id: int = Field(
        ..., description="The ID of the EOB missing a bank transaction."
    )
    payment_number: str = Field(..., description="Payment reference number.")
    payer_name: str = Field(..., description="Payer name from payer table.")
    payment_type: str = Field(
        ..., description="Payment type: ACH, CHECK, VCC, or NON_PAYMENT."
    )
    adjusted_amount: int = Field(
        ..., description="Expected deposit in cents (payment_amount + adjustments)."
    )


class MissingEOBTask(BaseModel):
    """Dashboard inbox task: a bank transaction with no matching EOB.
    Surfaced so the practice can manually reconcile the payment."""

    transaction_id: int = Field(
        ...,
        description="The ID of the bank transaction that is missing the EOB.",
    )
    payer_name: str | None = Field(
        None, description="Payer name, if inferable from transaction note."
    )
    payment_number: str | None = Field(
        None, description="Payment number, if inferable from transaction note."
    )
    amount: int = Field(
        ...,
        description="The amount in cents of the transaction.",
    )
    received_at: datetime = Field(
        ...,
        description="The date and time the transaction was received.",
    )


class ReconciliationStats(BaseModel):
    """Aggregate statistics for classification and reconciliation."""

    total_transactions: int = Field(..., description="Total bank transactions.")
    insurance_count: int = Field(..., description="Transactions classified as insurance.")
    not_insurance_count: int = Field(
        ..., description="Transactions classified as not insurance."
    )
    unknown_count: int = Field(
        ..., description="Transactions with unknown classification."
    )
    total_eobs: int = Field(..., description="Total EOBs.")
    matched_count: int = Field(..., description="EOBs with a match.")
    unmatched_eob_count: int = Field(
        ..., description="EOBs without a matching transaction."
    )
    unmatched_txn_count: int = Field(
        ..., description="Insurance transactions without a matching EOB."
    )
    manual_match_count: int = Field(
        ..., description="Matches created manually by user."
    )
    auto_match_count: int = Field(
        ..., description="Matches created by automated matchers."
    )
    match_by_method: dict[str, int] = Field(
        default_factory=dict,
        description="Count per match method (payment_number, payer_amount_date, manual, etc.).",
    )


class PaginatedResult(BaseModel, Generic[T]):
    """Paginated result container with metadata."""

    items: list[T]
    total_count: int
    page: int  # 0-indexed
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total pages (ceiling division)."""
        if self.page_size <= 0:
            return 0
        return (self.total_count + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """Check if next page exists."""
        return self.page < self.total_pages - 1

    @property
    def has_prev(self) -> bool:
        """Check if previous page exists."""
        return self.page > 0
