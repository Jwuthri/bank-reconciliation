---
name: Refactor for Best Practices
overview: Clean up DRY violations, add a Matcher protocol, consolidate payer-name mappings, fix the base class gap, replace deprecated FastAPI startup hook, and update tests accordingly.
todos:
  - id: remove-duplicate-cli
    content: Delete match_all(), _print_dashboard(), main() from matchers.py (lines 271-476) and _print_dashboard(), main() from classifier.py (lines 347-522)
    status: completed
  - id: add-matcher-protocol
    content: Add Matcher protocol to matchers.py; refactor engine.run_matching() to loop over list[Matcher]
    status: completed
  - id: remove-hardcoded-payer-map
    content: Delete DEFAULT_PAYER_NOTE_MAP, make payer_note_map required on PayerAmountDateMatcher; update scripts/ imports
    status: completed
  - id: consolidate-payer-registry
    content: Create single payer-name mapping source; refactor _infer_payer_name and build_payer_note_map_from_db to use it
    status: completed
  - id: fix-base-class
    content: Add run_matching() to ReconciliationEngine base class with default no-opReplace @app.on_event('startup') with lifespan context manager in dashboard.py
    status: completed
  - id: run-tests
    content: Run pytest tests/ -v to verify all tests pass after refactoring
    status: completed
isProject: false
---

# Refactor Reconciliation Codebase for Best Practices

## 1. Remove duplicated `match_all` / CLI code from matchers.py

[matchers.py](bank_reconciliation/reconciliation/matchers.py) lines 271-476 contain `match_all()`, `_print_dashboard()`, and `main()` -- a full standalone pipeline that duplicates what `LiveReconciliationEngine.run_matching()` already does in [engine.py](bank_reconciliation/reconciliation/engine.py). Delete all of it (lines 271-476). The matchers module should only export matcher classes and helpers.

Similarly, [classifier.py](bank_reconciliation/reconciliation/classifier.py) lines 347-522 contain `_print_dashboard()` and `main()` -- standalone CLI code. Delete those too. The classifier module should only export `classify_transaction`, `classify_all`, `Classification`, and the `RULES` list.

## 2. Add a `Matcher` protocol

Add a `Matcher` protocol to [matchers.py](bank_reconciliation/reconciliation/matchers.py) so both matchers share a formal interface:

```python
class Matcher(Protocol):
    def match(
        self,
        transactions: Sequence[BankTransactionLike],
        *,
        already_matched_eob_ids: set[int] | None = None,
        already_matched_txn_ids: set[int] | None = None,
    ) -> list[MatchResult]: ...
```

Then refactor `run_matching()` in [engine.py](bank_reconciliation/reconciliation/engine.py) to iterate over a `list[Matcher]` instead of hardcoding two matcher calls. This makes adding a third matcher trivial.

## 3. Remove `DEFAULT_PAYER_NOTE_MAP` with hardcoded IDs

Delete `DEFAULT_PAYER_NOTE_MAP` (line 148-152 of [matchers.py](bank_reconciliation/reconciliation/matchers.py)). Make `payer_note_map` a **required** parameter on `PayerAmountDateMatcher.__init`__ (remove the `None` default and the fallback on line 186). This forces callers to build the map from the DB via `build_payer_note_map_from_db()`.

Update [test_matchers.py](tests/unit/test_matchers.py) -- the tests already pass an explicit `PAYER_NOTE_MAP`, so they only need the `_make_matcher` helper adjusted (remove the `or self.PAYER_NOTE_MAP` fallback since it's now required).

The two scripts in `scripts/` that import `DEFAULT_PAYER_NOTE_MAP` will need their import removed or replaced with `build_payer_note_map_from_db`.

## 4. Consolidate payer-name mappings into a single source of truth

Currently payer-to-note knowledge lives in three places:

- `_PAYER_PATTERNS` + `_HCCLAIMPMT_PAYER_CODES` in [engine.py](bank_reconciliation/reconciliation/engine.py) (lines 41-62)
- `_KNOWN` dict inside `build_payer_note_map_from_db` in [matchers.py](bank_reconciliation/reconciliation/matchers.py) (lines 161-166)
- `_identify_payer` logic in `PayerAmountDateMatcher`

Create a single `payer_registry.py` module (or a top-level dict in `matchers.py`) that is the canonical mapping. Both `_infer_payer_name` (engine) and `build_payer_note_map_from_db` (matchers) should reference it.

## 5. Add `run_matching` to the base class

[base.py](bank_reconciliation/reconciliation/base.py) defines `ReconciliationEngine` with 3 query methods but no `run_matching`. The dashboard types the engine as `ReconciliationEngine` yet calls `engine.run_matching()`. Add it to the base class with a default no-op:

```python
def run_matching(self, **kwargs) -> dict[str, int]:
    return {}
```

## 7. Update tests

- [test_matchers.py](tests/unit/test_matchers.py): `PayerAmountDateMatcher` now requires `payer_note_map` -- tests already pass it explicitly, just verify nothing breaks.
- [test_engine.py](tests/unit/test_engine.py): No structural changes needed, but run full suite to confirm.
- Run `pytest tests/ -v` at the end to verify all tests pass.

