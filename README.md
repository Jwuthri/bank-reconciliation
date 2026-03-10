# Lassie – Bank Reconciliation Take-Home

## Overview

Lassie is building the AI platform to run the modern dental office, starting with insurance payments and posting. Our current product automates collecting insurance payment data from payer portals (Aetna, Delta Dental, MetLife, and more) and matches these with bank transactions—so practices can streamline their workflow, reduce manual effort, and get a clear view of their finances.

Your job is to implement the **reconciliation engine**: the system that matches bank transactions to payment records / explanation of benefits (EOBs) and flags anything it can't resolve.

## Background

### EOBs and Bank Transactions

**EOB (Explanation of Benefits)**
Payment record from insurance payer portal showing:

- Payer (e.g., Aetna, Delta Dental)
- Payment date
- Amount (payment_amount and adjusted_amount after payment-level adjustments)
- Payment number (check/payment reference)
- Payment type (ACH, CHECK, VCC)

**Bank Transaction**
Raw deposit in practice's business bank account showing:

- Amount (in cents)
- Note/memo (often generic or cryptic)
- Date received

The reconciliation engine matches these two sources to confirm expected payments actually arrived.

### Why reconciliation is hard

Bank transaction notes are often generic:

```
ACH DEP HNB - ECHO *8386
ACH DEP ZP UHCDCOMM5044 *9299
MetLife
Delta Dental
ACH CREDIT PNC-ECHO HCCLAIMPMT ON 02/24
```

Or be completely unrelated to insurance payments:

```
PAYROLL
rent
PAYMENT TO COMMERCIAL LOAN ...
SERVICE CHARGE
ADMIN NETWORKS SALE
```

**Matching examples:**

**UHC Transaction**
Bank: `02/24 $2,100 "ACH DEP ZP UHCDCOMM5044 *9299"`
EOB: `UHC 02/24 $2,100 061220259299`
Payment number matches note suffix.

**Generic MetLife**
Bank: `02/24 $1,247.50 "MetLife"`
EOB1: `MetLife 02/24 $1,247.50`
EOB2: `MetLife 02/24 $623.75`
EOB3: `MetLife 02/23 $1,247.50`
Multiple candidates, only amount/date to distinguish.

**No Payer Identifier**
Bank: `02/24 $550 "ACH CREDIT PNC-ECHO HCCLAIMPMT ON 02/24"`
EOB: `Cigna 02/24 $550`
Note has no payer name, only date and amount.

**Delta Dental**
Bank: `02/24 $850 "Delta Dental"`
EOB: `Delta Dental of California 02/24 $850`
Payer name present but no payment number.

**Echo with Reference**
Bank: `02/23 $998.75 "ACH DEP HNB - ECHO *8386"`
EOB: `Aetna 02/23 $1,000 #8386`
Payment number matches but $1.25 fee, no payer name in note.

A good engine uses amounts, dates, note patterns, and history to resolve cases automatically.

### When Lassie flags a task

Lassie flags cases it cannot resolve automatically:

- A bank transaction has no matching payment record (EOB)
- A payment record (EOB) has no matching bank transaction

Tasks are raised when items remain unreconciled. The implementation determines the appropriate time threshold before flagging.

## Your Assignment

Implement the `ReconciliationEngine` class in `bank_reconciliation/reconciliation/`.

The hard part isn't the matching logic itself — it's deciding when you have enough confidence to match automatically and when to punt to the practice. No single signal is fully reliable: transaction notes are often too generic to identify a payer, and amounts can be thrown off by processing fees or other adjustments. The historical transaction data can reveal patterns in how specific payers tend to transmit funds, which may help resolve ambiguous cases. When multiple EOBs match the same transaction, you'll need to decide whether to pick the best candidate or raise a task.

## Rules

You have complete freedom over the codebase. You may restructure files, add tables or columns to the database, add scheduled tasks, and introduce new dependencies. AI assistance is permitted.

The one firm requirement: your implementation must fully respect the `ReconciliationEngine` interface as defined below.

## Database Schema

The SQLite database (`bank_reconciliation.db`) contains three tables.

### `payers`

| Column | Type    | Description                      |
| ------ | ------- | -------------------------------- |
| `id`   | INTEGER | Primary key                      |
| `name` | VARCHAR | e.g. `"Aetna"`, `"Delta Dental"` |

### `bank_transactions`

| Column        | Type     | Description                                             |
| ------------- | -------- | ------------------------------------------------------- |
| `id`          | INTEGER  | Primary key                                             |
| `amount`      | INTEGER  | Amount in cents                                         |
| `note`        | TEXT     | Memo/description, may be generic or contain payer hints |
| `received_at` | DATETIME | When the transaction was accrued                        |

### `eobs`

| Column            | Type     | Description                                                              |
| ----------------- | -------- | ------------------------------------------------------------------------ |
| `id`              | INTEGER  | Primary key                                                              |
| `payment_number`  | VARCHAR  | Check/payment reference number                                           |
| `payer_id`        | INTEGER  | Foreign key to `payers`                                                  |
| `payment_amount`  | INTEGER  | Original payment amount in cents                                         |
| `adjusted_amount` | INTEGER  | Amount after payment-level adjustments (processing fees, interest, etc.) |
| `payment_type`    | VARCHAR  | `"ACH"`, `"CHECK"`, `"VCC"`, or `"NON_PAYMENT"`                          |
| `payment_date`    | DATETIME | When the payer claims they sent a deposit                                |

The EOB may show a gross payment that differs from the actual deposit due to payer-level adjustments. Use `adjusted_amount` when matching against bank transactions. All monetary values are stored in cents (e.g. `$100.00 = 10000`).

## Understanding Dashboard Payments

The reconciliation engine produces a unified view where each "payment" represents either:

- A **reconciled pair**: An EOB matched to its corresponding bank transaction
- An **unmatched EOB**: An EOB awaiting its bank transaction
- An **unmatched transaction**: A bank transaction awaiting its EOB

### Status Fields

Each `DashboardPayment` has two status indicators:

- **`bank_transaction_status`**:
  - `AWAITING` — no bank transaction exists for this item
  - `RECEIVED` — bank transaction exists

- **`eob_status`**:
  - `AWAITING` — no EOB exists for this item
  - `RECEIVED` — EOB exists

A fully reconciled payment has both statuses as `RECEIVED`.

### `DashboardPayment` Fields

The dashboard's perspective of a payment: a matched pair, unmatched EOB, or unmatched bank transaction. Each row in the Payments view maps to one of these. Fields from the missing side are `None`.

| Field                      | Type              | Description                                                    |
| -------------------------- | ----------------- | -------------------------------------------------------------- |
| `eob_id`                   | `int \| None`     | EOB ID, present when an EOB exists                             |
| `transaction_id`           | `int \| None`     | Bank transaction ID, present when a transaction exists         |
| `payer_name`               | `str \| None`     | Payer name from EOB or inferred from transaction note          |
| `payment_number`           | `str \| None`     | Payment reference number from EOB                              |
| `payment_amount`           | `int \| None`     | Base payment amount in cents from EOB                          |
| `adjusted_amount`          | `int \| None`     | `payment_amount` + adjustments (expected deposit), or bank txn amount |
| `date`                     | `datetime`        | EOB `payment_date` or bank transaction `received_at`           |
| `bank_transaction_status`  | `Literal`         | `"AWAITING"` or `"RECEIVED"`                                   |
| `eob_status`               | `Literal`         | `"AWAITING"` or `"RECEIVED"`                                   |

### `MissingTransactionTask` Fields

Inbox task: an EOB with no matching bank transaction. Surfaced so the practice can manually reconcile the payment.

| Field              | Type   | Description                                       |
| ------------------ | ------ | ------------------------------------------------- |
| `eob_id`           | `int`  | EOB ID                                            |
| `payment_number`   | `str`  | Payment reference number                          |
| `payer_name`       | `str`  | Payer name                                        |
| `payment_type`     | `str`  | `"ACH"`, `"CHECK"`, `"VCC"`, or `"NON_PAYMENT"`  |
| `adjusted_amount`  | `int`  | Expected deposit amount in cents                  |

### `MissingEOBTask` Fields

Inbox task: a bank transaction with no matching EOB. Surfaced so the practice can manually reconcile the payment.

| Field              | Type            | Description                                            |
| ------------------ | --------------- | ------------------------------------------------------ |
| `transaction_id`   | `int`           | Bank transaction ID                                    |
| `payer_name`       | `str \| None`   | Payer name, if inferable from transaction note         |
| `payment_number`   | `str \| None`   | Payment number, if inferable from transaction note     |
| `amount`           | `int`           | Transaction amount in cents                            |
| `received_at`      | `datetime`      | When the transaction was received                      |

## `ReconciliationEngine` Interface

The following interface must be respected. Implement each method in `bank_reconciliation/reconciliation/`.

```python
class ReconciliationEngine:
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
```

---

## Data

The included database contains ~1 year of bank transactions and EOBs. Your solution will be evaluated against ~4 years of data, so avoid overfitting to the provided dataset.

## Getting Started

```bash
# Install python
uv python install 3.12

# Install dependencies
uv sync --all-extras

# Run the dashboard web server (http://localhost:8000)
uv run poe dashboard

# Run tests
uv run poe test
```

### CLI

```bash
# List dashboard payments (matched pairs, unmatched EOBs, unmatched transactions)
uv run poe cli list:payments --page 1 --page-size 20

# List EOBs missing a bank transaction
uv run poe cli list:missing-transactions --page 1 --page-size 10

# List bank transactions missing an EOB
uv run poe cli list:missing-payment-eob --page 1 --page-size 15
```

| Flag          | Default | Description                |
| ------------- | ------- | -------------------------- |
| `--page`      | `1`     | Page number (1-indexed)    |
| `--page-size` | `20`    | Number of results per page |
