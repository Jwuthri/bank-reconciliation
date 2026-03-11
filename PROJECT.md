# Bank Reconciliation — Project Summary

## What It Does

Matches bank transactions to insurance EOBs (Explanation of Benefits) so dental practices can reconcile payments. Two-stage pipeline: (1) **classify** transactions as insurance or not, (2) **match** insurance transactions to EOBs via payment number or payer+amount+date.

---

## Pipeline Flow (`engine.run_matching()`)

```mermaid
flowchart TB
    subgraph CLASSIFY["1. CLASSIFY (classify_all)"]
        direction TB
        C1["Pass 1: Rules (fast, free)"]
        C2[Insurance: HCCLAIMPMT, MetLife, CALIFORNIA DENTA, Guardian]
        C3[Noise: PAYROLL, rent, BNKCD, Simplifeye, etc.]
        C4{Unknown?}
        C5[Precision: default to NOT insurance]
        C6["Pass 2: LLM (only unknowns, minimized for cost/speed)"]
        C7[(transaction_classifications)]
        C1 --> C2
        C1 --> C3
        C2 -->|Matched| C7
        C3 -->|Matched| C7
        C1 --> C4
        C4 -->|no-llm / Precision mode| C5
        C4 -->|use_llm=True| C6
        C5 --> C7
        C6 --> C7
    end

    subgraph MATCH["2. MATCH (sequential, high-confidence first)"]
        direction TB
        M1[PaymentNumberMatcher]
        M1a["TRN*1*&lt;NUM&gt;* in note → lookup EOB by payment_number"]
        M1b["Confidence: 1.0 (exact) or 0.9 (within $5 fee)"]
        M1c["~1,995 matches"]
        M2[PayerAmountDateMatcher]
        M2a["Payer in note + amount + date window (14 days)"]
        M2b["Confidence: 0.85 (unique) or 0.7 (ambiguous)"]
        M2c["~844 matches"]
        M3[(reconciliation_matches)]
        M1 --> M1a --> M1b --> M1c
        M1c -->|Already-matched IDs passed to exclude| M2
        M2 --> M2a --> M2b --> M2c
        M2c --> M3
    end

    subgraph QUERY["3. QUERY (interface methods)"]
        direction TB
        Q1[get_dashboard_payments]
        Q1a["Matched pairs + unmatched EOBs + unmatched insurance txns"]
        Q2[get_missing_bank_transactions]
        Q2a["Unmatched EOBs (excl. zero-dollar NON_PAYMENTs)"]
        Q3[get_missing_payment_eobs]
        Q3a["Unmatched insurance txns (noise filtered out)"]
        Q1 --> Q1a
        Q2 --> Q2a
        Q3 --> Q3a
    end

    CLASSIFY --> MATCH
    MATCH --> QUERY
```

---

## Findings (Short)

- **EOB matching accuracy is strong** — Most EOBs are matched successfully.
- **Both match rates matter:**
  - **EOBs → transactions**: 3,293 of 3,526 EOBs matched to a bank transaction (~93%); ~233 unmatched EOBs.
  - **Insurance txns → EOBs**: 2,839 of 5,238 insurance transactions matched to an EOB (~54%).
- **Main gap**: 1,677 have TRN payment numbers in notes but no EOB with that `payment_number` — bank and EOB data use different schemes or time periods. Not fixable by code.
- **Other gaps**: 571 have payer in note but no EOB for that payer+amount; 125 fail date window; 9 have amount mismatch > $5.

### Opportunities to Expand Match Rate

1. **Relax constraints** — Consider loosening date window (e.g. 14 → 21 days), amount tolerance (e.g. $5 → $10), or confidence thresholds to capture more borderline matches (with manual review where needed).
2. **Insurance classifier improvement** — Some transactions may be misclassified as NOT insurance, so they never enter the matching pipeline. Expanding rule coverage is the priority (free and fast); LLM prompts are tuned only for the remaining unknowns.

---

## Is Insurance Classification

Before matching, we classify each transaction as **insurance** or **not** (noise). Only insurance transactions are matched to EOBs and surfaced as "missing EOB" tasks.

**Design goal: minimize LLM usage.** The LLM is expensive and slow relative to rules. We use it only as a second-pass fallback — the vast majority of transactions are resolved by deterministic rules alone, keeping cost near-zero and latency low.

1. **First pass — Rules** (fast, free): Regex patterns resolve most transactions immediately. Insurance patterns (HCCLAIMPMT, MetLife, Guardian, CALIFORNIA DENTA) and noise patterns (payroll, rent, card settlement, fees, etc.) cover the bulk of the data.
2. **Second pass — LLM** (only for unknowns): Only transactions that no rule matched are sent to gpt-5-mini. This is a small fraction of the total volume. Use `--no-llm` to disable entirely and fall back to precision mode (default to NOT insurance).
- **Confidence**: Rule matches = 1.0; LLM = 0.5; unresolved unknowns = 0.0. Stored in `transaction_classifications.confidence`.

---

## Precision vs Recall — Why Precision

For **unknown** transactions (no rule, no LLM), we choose how to treat them:

| Mode | Unknowns treated as | Effect |
|------|---------------------|--------|
| **Precision** (default) | NOT insurance | Fewer false positives; some real insurance may be missed. |
| **Recall** | Insurance | Catch more insurance; more false positives (noise flagged as missing EOB). |

**We default to precision** because this is real money for real people. A false positive means we tell a practice "you have an insurance payment with no EOB" when it's actually payroll, rent, or a vendor — wasting their time and eroding trust. Missing a true insurance transaction is less harmful: it stays in the bank feed and can be reconciled later. Better to under-flag than over-flag.

---

## Future Improvements

### Production Architecture

15. **Event-driven ingestion with delayed matching** — In production, don't match instantly or wait for a nightly batch. Ingest data as it arrives (bank feed via Plaid/MX every ~15 min, EOBs via 835 EDI/SFTP every few hours), then schedule a reconciliation job with a **2–4 hour delay**. This gives the counterpart record time to arrive before matching, avoiding false "missing" tasks that resolve themselves. The delay is tunable per payer.
16. **Nightly sweep as safety net** — A nightly cron re-attempts matching on anything still unmatched (the counterpart may have arrived since the delayed job ran), generates daily summary reports, and handles edge cases like retroactive EOB corrections. This is the catch-all, not the primary matching trigger.
17. **Multi-tenancy** — Each dental practice is a tenant. The matching engine runs per-practice with tenant isolation in the database (row-level or schema-per-tenant) and job queue. Tenant ID should be threaded through all queries and engine methods. In the current codebase, the single-DB design works for the take-home but would need partitioning or a connection-per-tenant approach in production.
18. **Task queue infrastructure** — Replace in-process `engine.run_matching()` with a proper job queue (Celery + Redis, AWS SQS, or GCP Cloud Tasks). Each ingestion event enqueues a delayed reconciliation job. The nightly sweep is a scheduled Celery Beat task. This decouples ingestion from matching and allows horizontal scaling.
19. **Postgres over SQLite** — SQLite is fine for the take-home but doesn't support concurrent writes, row-level locking, or multi-tenancy well. Production needs Postgres with proper indices on `(payment_number)`, `(payer_id, adjusted_amount)`, `(received_at)`, and `(bank_transaction_id)`.
20. **Confidence-driven automation** — Auto-confirm matches above 0.95 confidence without human review. Surface matches between 0.7–0.95 for manual confirmation. Below 0.7, surface as a task. This reduces inbox noise while maintaining accuracy.
21. **Audit trail and compliance** — Every match (auto or manual) needs a full audit log: who matched it, when, which method, what confidence, and the raw data at match time. Medical billing has compliance requirements (SOX for larger orgs). The current `ReconciliationMatch` table stores method and confidence but lacks user attribution and immutable snapshots.
22. **Observability and alerting** — Monitor unmatched rate over time. Alert when it spikes (could mean a payer changed their 835 format, the bank feed broke, or a new payer appeared). Dashboard showing match rate trends, average time-to-match, and classifier accuracy.

### Matching & Classification

1. **Insurance classifier expansion** — Add more rule patterns so fewer transactions fall through to the LLM. Every new rule reduces LLM calls (cost + latency) and improves match rate.
2. **Constraint relaxation** — Experiment with looser date window, amount tolerance, or confidence thresholds (with manual-review flags) to capture more borderline matches.
3. **TRN payment number alignment** — Investigate why bank TRN numbers don't match EOB `payment_number`. May need data pipeline changes, format normalization, or upstream integration.
4. **LLM tuning** — For the remaining unknowns that still require LLM, tune prompts and evaluate cost vs accuracy. Goal: keep LLM usage as small as possible.
5. **More payer patterns** — Add Beam, GEHA, Humana, UMR, etc. to `payer_note_map` as patterns are discovered.
6. **HCCLAIMPMT payer code mapping** — Use clearinghouse codes (UHCDComm, PAY PLUS, DELTADENTALCA) to infer payer for amount+date matching when TRN fails.
7. **Adaptive date window** — Use payer-specific windows (e.g. MetLife vs ACH) based on historical settlement patterns.
8. **Confidence thresholds** — Surface only matches above a threshold (e.g. 0.85) as auto-reconciled; lower-confidence for manual review.
9. **Amount-only with strong date** — For single EOB with same amount and very close date (e.g. 1–2 days), consider low-confidence match with explicit review flag.
10. **Duplicate payment_number handling** — Warn or disambiguate when multiple EOBs share the same `payment_number`.
11. **NON_PAYMENT EOBs** — Refine handling of zero-dollar and adjustment EOBs (GEHA, MetLife refunds).
12. **CHECK-type matching** — Improve matching of paper-check EOBs to REMOTE DEPOSIT CAPTURE transactions.

### Performance

13. **Batch DB writes** — All classification and match results are inserted in batches of 500 within a single transaction, avoiding N+1 inserts.
14. **Indexed lookups in matchers** — `PaymentNumberMatcher` builds a `dict[str, EOB]` keyed by normalized payment number (O(1) lookup). `PayerAmountDateMatcher` indexes EOBs by `(payer_id, adjusted_amount)` for O(1) candidate retrieval, then filters by date window.
15. **Idempotent pipeline** — `classify_all` and `run_matching` skip already-processed records, so re-runs are cheap. Only new/unmatched items are processed.
16. **LLM minimization** — Rules resolve ~87% of transactions for free. The LLM is only called for the remaining unknowns, with concurrency-limited async calls (8 concurrent). This keeps cost near-zero and latency low for the common case.
17. **In production: horizontal scaling** — With a task queue (Celery/SQS), matching jobs can run on multiple workers in parallel, one per tenant. The matching engine is stateless — all state lives in the DB.

### Generalization (Avoid Overfitting)

18. **Tested against unseen data** — The provided DB has ~1 year of data; the solution will be evaluated against ~4 years. All rules, patterns, and thresholds are designed to generalize: regex patterns use broad payer-name matching (not specific IDs), date windows and amount tolerances are configurable, and the LLM fallback handles novel note formats. The `payer_registry` is a lookup table that can grow without code changes.
19. **Historical pattern learning** — In production, analyze how specific payers transmit funds over time (typical delay between EOB date and bank deposit, common note formats, fee patterns). Use these learned patterns to set per-payer confidence adjustments and date windows rather than global defaults.

---

## Demo Video

A 77-second walkthrough video covers the full system: the problem space, two-stage pipeline architecture, both matcher deep dives (PaymentNumberMatcher and PayerAmountDateMatcher), a live dashboard recording, and results.

**Where to find it:** `video/out/demo.mp4`

To re-render or preview interactively:

```bash
cd video
npm install              # first time only
npm run studio           # opens Remotion Studio at http://localhost:3000
npm run render           # renders to video/out/demo.mp4
npm run capture          # re-records the live dashboard (requires dashboard running at localhost:8000)
```
