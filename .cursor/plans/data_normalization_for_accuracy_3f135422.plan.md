---
name: Data Normalization for Accuracy
overview: Add a central normalization layer and apply it across the classifier, matchers, and payer registry to improve matching accuracy.
todos:
  - id: create-normalize-module
    content: Create normalize.py with normalize_note and normalize_payment_number
    status: completed
  - id: classifier-normalization
    content: Apply normalize_note in classifier, relax MetLife rule, add Delta Dental rules
    status: completed
  - id: matchers-normalization
    content: Apply normalization in extract_trn, PaymentNumberMatcher, _identify_payer; case-insensitive payer map
    status: completed
  - id: payer-registry-variants
    content: Add HCCLAIMPMT code variants (HNB-ECHO, PNCECHO) to payer_registry
    status: completed
  - id: engine-infer-payer
    content: Apply normalize_note in _infer_payer_name
    status: completed
  - id: add-tests
    content: Add unit tests for normalization edge cases; run full test suite
    status: completed
isProject: false
---

# Data Normalization for Accuracy

## 1. Create central normalization module

Create [bank_reconciliation/reconciliation/normalize.py](bank_reconciliation/reconciliation/normalize.py) with:

- `normalize_note(note: str | None) -> str` — strip, collapse multiple spaces, return `""` for None
- `normalize_payment_number(s: str | None) -> str | None` — strip, remove non-alphanumeric chars, return None if empty

## 2. Apply note normalization in classifier

In [bank_reconciliation/reconciliation/classifier.py](bank_reconciliation/reconciliation/classifier.py):

- At the start of `classify_transaction`, call `normalize_note(note)` and use the result for rule matching
- Relax MetLife rule: change `^MetLife$` to `^MetLife\s*$` or `\bMetLife\b` to tolerate trailing whitespace
- Add insurance rules for `Delta Dental` and `DELTA DENTAL` (substring match) so notes without "CALIFORNIA DENTA" still classify as insurance

## 3. Apply normalization in matchers

In [bank_reconciliation/reconciliation/matchers.py](bank_reconciliation/reconciliation/matchers.py):

- In `extract_trn_payment_number`: after extracting, return `normalize_payment_number(extracted)` instead of raw value
- In `PaymentNumberMatcher.__init`__: when building `_eob_by_payment_number`, use `normalize_payment_number(eob.payment_number)` as the key (with fallback to raw if normalized is empty)
- In `PaymentNumberMatcher.match`: use `normalize_payment_number(extract_trn_payment_number(bt.note))` for lookup (extract_trn already normalizes, or we normalize in extract_trn)
- In `_identify_payer`: pass `normalize_note(note)` before the pattern check, or normalize note at the start of the method

## 4. Payer name case-insensitivity

In [bank_reconciliation/reconciliation/matchers.py](bank_reconciliation/reconciliation/matchers.py) `build_payer_note_map_from_db`:

- Change `p.name.startswith(name_prefix)` to `p.name.lower().startswith(name_prefix.lower())`

## 5. HCCLAIMPMT code variants in payer_registry

In [bank_reconciliation/reconciliation/payer_registry.py](bank_reconciliation/reconciliation/payer_registry.py):

- Add variant entries for codes with spacing: e.g. `"HNB-ECHO"` -> None (alias for `"HNB - ECHO"`), `"PNCECHO"` -> None (alias for `"PNC-ECHO"`)

## 6. Apply normalization in engine._infer_payer_name

In [bank_reconciliation/reconciliation/engine.py](bank_reconciliation/reconciliation/engine.py):

- At the start of `_infer_payer_name`, call `normalize_note(note)` and use that for pattern lookups

## 7. Update tests

- Add unit tests in `tests/unit/test_classifier.py` for: `"MetLife "`, `" MetLife"`, `"Delta Dental"`, `"DELTA DENTAL"`
- Add unit tests in `tests/unit/test_matchers.py` for: `normalize_payment_number` (or `extract_trn_payment_number` with normalized output), payment number with dashes/spaces
- Ensure existing tests still pass

