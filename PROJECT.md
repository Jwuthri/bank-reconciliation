# Bank Reconciliation — Project Summary

## What It Does

Matches bank transactions to insurance EOBs (Explanation of Benefits) so dental practices can reconcile payments. Two-stage pipeline: (1) **classify** transactions as insurance or not, (2) **match** insurance transactions to EOBs via payment number or payer+amount+date.

---

## Pipeline Flow (`engine.run_matching()`)

```mermaid
flowchart TB
    subgraph CLASSIFY["1. CLASSIFY (classify_all)"]
        direction TB
        C1[Rules first]
        C2[Insurance: HCCLAIMPMT, MetLife, CALIFORNIA DENTA, Guardian]
        C3[Noise: PAYROLL, rent, BNKCD, Simplifeye, etc.]
        C4{Unknown?}
        C5[Precision: default to NOT insurance]
        C6[use_llm: send to LLM]
        C7[(transaction_classifications)]
        C1 --> C2
        C1 --> C3
        C2 -->|Matched| C7
        C3 -->|Matched| C7
        C1 --> C4
        C4 -->|Precision mode| C5
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
2. **Insurance classifier improvement** — Some transactions may be misclassified as NOT insurance, so they never enter the matching pipeline. Improving rule coverage and LLM prompts could surface more insurance transactions and increase the match rate.

---

## Is Insurance Classification

Before matching, we classify each transaction as **insurance** or **not** (noise). Only insurance transactions are matched to EOBs and surfaced as "missing EOB" tasks.

- **Rule-based**: Regex patterns for HCCLAIMPMT, MetLife, Guardian, CALIFORNIA DENTA (insurance) vs payroll, rent, card settlement, fees, etc. (noise).
- **LLM fallback** (default): Unknowns sent to gpt-5-mini for a second opinion. Use `--no-llm` to disable.
- **Confidence**: Rule matches = 1.0; unknowns = 0.0; LLM = 0.5. Stored in `transaction_classifications.confidence`.

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

1. **Insurance classifier expansion** — Improve rule coverage and LLM prompts so fewer true insurance transactions are classified as NOT insurance; this directly expands the match rate.
2. **Constraint relaxation** — Experiment with looser date window, amount tolerance, or confidence thresholds (with manual-review flags) to capture more borderline matches.
3. **TRN payment number alignment** — Investigate why bank TRN numbers don't match EOB `payment_number`. May need data pipeline changes, format normalization, or upstream integration.
4. **LLM tuning** — LLM is default for unknowns; tune prompts and evaluate cost vs accuracy.
5. **More payer patterns** — Add Beam, GEHA, Humana, UMR, etc. to `payer_note_map` as patterns are discovered.
6. **HCCLAIMPMT payer code mapping** — Use clearinghouse codes (UHCDComm, PAY PLUS, DELTADENTALCA) to infer payer for amount+date matching when TRN fails.
7. **Adaptive date window** — Use payer-specific windows (e.g. MetLife vs ACH) based on historical settlement patterns.
8. **Confidence thresholds** — Surface only matches above a threshold (e.g. 0.85) as auto-reconciled; lower-confidence for manual review.
9. **Amount-only with strong date** — For single EOB with same amount and very close date (e.g. 1–2 days), consider low-confidence match with explicit review flag.
10. **Duplicate payment_number handling** — Warn or disambiguate when multiple EOBs share the same `payment_number`.
11. **NON_PAYMENT EOBs** — Refine handling of zero-dollar and adjustment EOBs (GEHA, MetLife refunds).
12. **CHECK-type matching** — Improve matching of paper-check EOBs to REMOTE DEPOSIT CAPTURE transactions.
13. **Scheduled reconciliation** — Run matching on a schedule; configurable timeout before surfacing tasks.
14. **Audit trail** — Log match decisions (method, confidence) for debugging and compliance.
