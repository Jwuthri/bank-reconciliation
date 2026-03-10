# Bank Reconciliation Engine -- Task Breakdown

## Context

Lassie is building an AI platform for dental offices. Their current product automates collecting insurance payment data from payer portals (Aetna, Delta Dental, MetLife, etc.) and matches these with bank transactions so practices can streamline finances and reduce manual work.

Your job: implement the **reconciliation engine** that matches bank transactions to EOB (Explanation of Benefits) records, and flags anything it can't resolve as a task for the practice to follow up on manually.

---

## What You're Building

You need to implement the `ReconciliationEngine` class in `bank_reconciliation/reconciliation/`. It currently has a stub interface in `base.py` with three methods that raise `NotImplementedError`. A `DummyReconciliationEngine` in `dummy_engine.py` returns fake data and powers the dashboard/CLI right now -- your real engine replaces it.

### The Three Methods

| Method | Returns | Purpose |
|--------|---------|---------|
| `get_dashboard_payments(page, page_size)` | `PaginatedResult[DashboardPayment]` | Unified view: matched EOB+transaction pairs, unmatched EOBs, and unmatched transactions. Ordered newest first. |
| `get_missing_bank_transactions(page, page_size)` | `PaginatedResult[MissingTransactionTask]` | EOBs that have no matching bank transaction (practice needs to investigate). |
| `get_missing_payment_eobs(page, page_size)` | `PaginatedResult[MissingEOBTask]` | Bank transactions that have no matching EOB (practice needs to investigate). |

### Core Matching Logic

Match EOBs to bank transactions by combining multiple signals:

1. **Amount**: Compare EOB `adjusted_amount` to bank transaction `amount` (both in cents). Allow small tolerances for processing fees (e.g., ~$1-2 for ACH fees).
2. **Date**: EOB `payment_date` should be close to transaction `received_at`. ACH typically settles in 1-3 business days; checks can take longer.
3. **Payment number / reference**: The EOB `payment_number` sometimes appears as a suffix in the bank transaction `note` (e.g., EOB `061220259299` matches note `*9299`).
4. **Payer name**: The transaction `note` sometimes contains the payer name (e.g., `"MetLife"`, `"Delta Dental"`). Match against the `payers` table. Names may be partial or variant (e.g., `"Delta Dental of California"` vs `"Delta Dental"`).
5. **Historical patterns**: The database contains ~1 year of data. Specific payers may have consistent note patterns that can be learned.

### Task Surfacing -- What to Flag

Two types of tasks for the practice inbox:

- **Missing bank transaction** (`MissingTransactionTask`): An EOB exists but no bank deposit matches it. The practice should check if the payment arrived.
- **Missing EOB** (`MissingEOBTask`): A bank deposit exists but no EOB matches it. The practice should find the corresponding insurance payment record.

**Critical from the interview**: Do NOT surface noise. The bank account is a regular business account with payroll, rent, loan payments, Porsche payments, etc. You must filter out non-insurance transactions before flagging them as missing EOBs. Surfacing irrelevant tasks destroys trust in the product.

---

## Key Challenges

### 1. Bank Transaction Notes Are Unreliable
Notes range from helpful to useless:
- Good: `"ACH DEP ZP UHCDCOMM5044 *9299"` (contains payer hint + reference number suffix)
- Medium: `"MetLife"` or `"Delta Dental"` (payer name only, no reference)
- Bad: `"ACH CREDIT PNC-ECHO HCCLAIMPMT ON 02/24"` (no payer, just a date)
- Irrelevant: `"PAYROLL"`, `"rent"`, `"SERVICE CHARGE"` (not insurance at all)

### 2. Amounts Don't Always Match Exactly
EOB `adjusted_amount` may differ from the bank transaction `amount` due to processing fees, interest, or other payer-level adjustments (e.g., $1.25 ACH fee on a $1,000 payment).

### 3. Multiple Candidates
Multiple EOBs can match the same transaction (same payer, same date, same amount). You need a confidence-scoring approach to pick the best match or punt to the practice when ambiguous.

### 4. Batch Deposits
Some payers batch multiple EOBs into a single bank deposit. The transaction amount equals the sum of several EOB `adjusted_amount` values.

### 5. Don't Overfit
The provided database has ~1 year of data (8,611 transactions, 3,526 EOBs, 26 payers). Your solution will be tested against ~4 years of data. Build general heuristics, not rules tuned to this specific dataset.

---

## What They're Evaluating

From the interview, the emphasis is on:

1. **System design** -- Clean architecture, separation of concerns, how you structure the matching pipeline.
2. **Trade-offs** -- Which heuristics you choose, how you handle ambiguity, when you auto-match vs. flag for review. Document your reasoning.
3. **Performance** -- Think about how this scales. Consider indexing, query efficiency, avoiding N+1 queries.
4. **Multi-tenancy** -- Think about how this would work for multiple dental practices (even if you don't implement it).
5. **Noise filtering** -- Don't flood the practice with irrelevant tasks. A Porsche payment should not generate a "missing EOB" task.
6. **Not 100% accuracy required** -- They explicitly said it doesn't need to be perfect. Focus on good design and reasonable matching over edge-case perfection.

---

## Data Available

### Database: `bank_reconciliation.db` (SQLite)

| Table | Rows | Key Fields |
|-------|------|------------|
| `payers` | 26 | `id`, `name` |
| `bank_transactions` | 8,611 | `id`, `amount` (cents), `note`, `received_at` |
| `eobs` | 3,526 | `id`, `payment_number`, `payer_id`, `payment_amount`, `adjusted_amount`, `payment_type`, `payment_date` |

Date range: 2024-09-09 to 2025-09-09.

### Pydantic Models (already defined in `bank_reconciliation/reconciliation/models.py`)
- `DashboardPayment` -- unified view row
- `MissingTransactionTask` -- EOB missing its bank transaction
- `MissingEOBTask` -- bank transaction missing its EOB
- `PaginatedResult[T]` -- generic paginated wrapper

### ORM Models (already defined in `bank_reconciliation/db/models.py`)
- `Payer`, `BankTransaction`, `EOB` -- Peewee models mapped to the SQLite tables

---

## Rules and Freedoms

- **Must respect** the `ReconciliationEngine` interface (the 3 methods, their signatures, return types).
- **Complete freedom** otherwise: restructure files, add database tables/columns, add scheduled tasks, add dependencies.
- **AI/LLM assistance permitted** -- you can use LLMs as part of the matching pipeline if you want.
- You can assume infrastructure like task queues or cron jobs exist.

---

## Suggested Implementation Plan

### Step 1: Understand the Data
Explore the database. Look at transaction notes, EOB patterns, payer names. Get a feel for what matching signals are available and how noisy the data is.

### Step 2: Build the Matching Pipeline
Create a multi-stage matcher:
1. **Filter non-insurance transactions** -- Classify bank transactions as insurance-related or not (payroll, rent, etc. should be excluded from matching and from "missing EOB" tasks).
2. **Exact match** -- Match on payment number reference found in transaction note + exact amount.
3. **Strong match** -- Payer name in note + amount match + date within window.
4. **Fuzzy match** -- Amount match + date proximity, possibly with small fee tolerance.
5. **Confidence scoring** -- Assign a score to each candidate match. Auto-match above a threshold, flag for review below it.

### Step 3: Handle Edge Cases
- Batch deposits (one transaction = sum of multiple EOBs).
- Fee adjustments (small amount differences).
- Multiple candidates with identical signals.

### Step 4: Implement the Three Interface Methods
- `get_dashboard_payments`: Query all EOBs and transactions, apply matching, return the unified view with status flags.
- `get_missing_bank_transactions`: Return unmatched EOBs (after a reasonable time threshold -- don't flag an EOB as missing if it was just created today).
- `get_missing_payment_eobs`: Return unmatched insurance-related transactions (filter out non-insurance noise).

### Step 5: Wire It Up
Replace `DummyReconciliationEngine` with your real engine in `dashboard.py` and `cli.py`.

### Step 6: Write Tests
Fill in the test stubs in `tests/test_reconcile.py`. The 8 test cases already outlined give you a roadmap:
- Exact match single payment
- Batch deposit (multiple payments)
- Fuzzy payer name matching
- Date window boundaries
- Unmatched transactions
- Unmatched payments
- Amount mismatch (no match)
- Different payment types

### Step 7: Consider Storing Match Results
You may want to add a table to persist reconciliation results (matched pairs, confidence scores) rather than recomputing on every API call. This is a design trade-off worth discussing.

---

## Running the Project

```bash
# Install Python 3.12
uv python install 3.12

# Install all dependencies
uv sync --all-extras

# Run the dashboard (http://localhost:8000)
uv run poe dashboard

# Run tests
uv run poe test

# CLI commands
uv run poe cli list:payments --page 1 --page-size 20
uv run poe cli list:missing-transactions --page 1 --page-size 10
uv run poe cli list:missing-payment-eob --page 1 --page-size 15
```

---

## Delivery

Zip the project and send it back via wormhole or email.
