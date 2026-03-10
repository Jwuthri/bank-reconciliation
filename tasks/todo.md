# Build Reconciliation Foundation — Task Tracker

## build-engine: Create engine.py implementing ReconciliationEngine with real DB queries

- [x] Read existing codebase (base engine, models, classifier, matchers, dummy engine, dashboard, CLI)
- [x] Write 21 failing tests covering run_matching, get_dashboard_payments, get_missing_bank_transactions, get_missing_payment_eobs
- [x] Implement `LiveReconciliationEngine` with `run_matching()` (classify → match → persist pipeline)
- [x] Implement `get_dashboard_payments()` — matched pairs + unmatched EOBs + unmatched insurance txns
- [x] Implement `get_missing_bank_transactions()` — unmatched EOBs (excluding zero-dollar NON_PAYMENTs)
- [x] Implement `get_missing_payment_eobs()` — unmatched insurance txns with payer/payment_number inference
- [x] Export `LiveReconciliationEngine` from `__init__.py`
- [x] Wire real engine into `dashboard.py` and `cli.py` (replacing DummyReconciliationEngine)
- [x] All 21 new tests pass, full suite (150 tests) green, zero lint errors

### Review

**Files created:**
- `bank_reconciliation/reconciliation/engine.py` — `LiveReconciliationEngine` with full pipeline + 3 query methods
- `tests/unit/test_engine.py` — 21 integration tests (in-memory SQLite)

**Files modified:**
- `bank_reconciliation/reconciliation/__init__.py` — exports `LiveReconciliationEngine`
- `bank_reconciliation/dashboard.py` — swapped `DummyReconciliationEngine` for `LiveReconciliationEngine`
- `bank_reconciliation/cli.py` — swapped `DummyReconciliationEngine` for `LiveReconciliationEngine`

**Design decisions:**
- `run_matching()` is a two-stage pipeline: classify all transactions, then run matchers in sequence (payment number first, payer+amount+date second), persisting results to `reconciliation_matches`
- `get_dashboard_payments()` builds a unified view from 3 sources: matched pairs (JOIN through reconciliation_matches), unmatched EOBs, and unmatched insurance transactions — sorted newest first
- Zero-dollar NON_PAYMENTs excluded from both dashboard unmatched EOBs and missing transactions
- Non-insurance (noise) transactions excluded from dashboard and missing EOBs
- `_infer_payer_name()` helper extracts payer name from note for missing EOB tasks
- Pagination done in Python for dashboard (3-source UNION), in SQL for the two task queries
- Idempotent: `run_matching()` skips already-matched EOBs/transactions

---

## build-matchers: Create matchers.py with PaymentNumberMatcher and PayerAmountDateMatcher

- [x] Read existing codebase (DB models, classifier, base engine, test patterns)
- [x] Investigate real data: TRN format, payer names, amount/date patterns
- [x] Write failing tests (31 test cases covering TRN extraction, both matchers, edge cases)
- [x] Implement `extract_trn_payment_number()` — regex extraction of `TRN*1*<NUM>*`
- [x] Implement `PaymentNumberMatcher` — TRN lookup with amount verification (1.0/0.9/skip)
- [x] Implement `PayerAmountDateMatcher` — payer+amount+date window matching (0.85/0.7)
- [x] All 31 new tests pass, full suite (121 tests) green, zero lint errors

### Review

**Files created:**
- `bank_reconciliation/reconciliation/matchers.py` — both matchers + `MatchResult` dataclass + `extract_trn_payment_number` utility
- `tests/unit/test_matchers.py` — 31 unit tests (pure functions, no DB)

**Design decisions:**
- Used Protocol-based duck typing so matchers work with both real DB models and lightweight fakes in tests
- `MatchResult` is a frozen dataclass matching the `ReconciliationMatch` DB model fields
- Both matchers accept `already_matched_eob_ids` / `already_matched_txn_ids` sets so the engine can chain matchers (payment number first, then payer+amount+date on the remainder)
- Fee tolerance of 500 cents for payment number matcher (confidence 0.9 vs 1.0)
- Date window defaults to 5 days, configurable per-instance
- Payer note map is configurable; defaults cover MetLife, Guardian Life, CALIFORNIA DENTA

---

## improve-engine-matchers: Fix bugs, expand coverage, wire everything up

- [x] Refactor `get_dashboard_payments` to use subqueries instead of loading all rows into memory
- [x] Expand `_infer_payer_name` with HCCLAIMPMT payer code extraction (14 payer codes)
- [x] Use `build_payer_note_map_from_db` in `engine.run_matching` (was passing `None`, falling back to hardcoded IDs)
- [x] Expand `build_payer_note_map_from_db` `_KNOWN` map with Delta Dental + `startswith` matching
- [x] Add duplicate `payment_number` warning in `PaymentNumberMatcher.__init__`
- [x] Add 7 missing noise rules to classifier: BKCD PROCESSING, RETURNED DEPOSIT, CHECK, Bill.com, Cherry, Outgoing Wire Fee, REMOTE DEPOSIT
- [x] Wire `LiveReconciliationEngine` into `dashboard.py` with startup hook (DB connect + init + run_matching)
- [x] Wire `LiveReconciliationEngine` into `cli.py` with DB connect/init/matching before commands
- [x] Fix `test_engine.py` MetLife `payer_id=3` hardcoding (no longer needed with `build_payer_note_map_from_db`)
- [x] Add 15 new test cases for new classifier noise rules
- [x] Update existing tests that expected new-rule notes to be "unknown"
- [x] All 157 tests pass, zero lint errors

### Review

**Files modified:**
- `bank_reconciliation/reconciliation/engine.py` — subquery-based pagination, expanded `_infer_payer_name`, `build_payer_note_map_from_db` usage
- `bank_reconciliation/reconciliation/matchers.py` — expanded `_KNOWN` map, `startswith` matching, duplicate payment_number warning
- `bank_reconciliation/reconciliation/classifier.py` — 7 new noise rules
- `bank_reconciliation/dashboard.py` — LiveEngine + startup hook with DB init + matching
- `bank_reconciliation/cli.py` — LiveEngine + DB init + matching before commands
- `tests/unit/test_engine.py` — removed payer_id=3 hardcoding
- `tests/unit/test_classifier.py` — 15 new noise rule tests, updated unknown tests
