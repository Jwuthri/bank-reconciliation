# Unmatched Transactions — Analysis & Findings

## Overview

After running the reconciliation matchers (PaymentNumberMatcher + PayerAmountDateMatcher), a portion of insurance-classified transactions remain unmatched. This document explains why and what was done to improve match rates.

**Current state (after improvements):**
- **Matched:** ~2,839 transactions (54.2% of 5,238 insurance transactions)
- **Unmatched:** ~2,399 transactions (45.8%)

---

## Unmatched Breakdown

### 1. By Classifier Label

| Label | Unmatched Count | Notes |
|-------|-----------------|-------|
| HCCLAIMPMT | ~1,686 | TRN payment number in note, but no EOB match |
| MetLife | ~699 | Payer+amount+date often fails (no EOB for that combo, or date outside window) |
| CALIFORNIA_DENTA | ~12 | Small volume |
| Guardian | ~2 | Small volume |

---

## Root Causes

### 2. TRN Payment Number Analysis

| Category | Count | Explanation |
|----------|-------|-------------|
| **Has TRN, NO EOB with that payment_number** | ~1,677 | Bank notes contain `TRN*1*<NUM>*` but the payment number does not exist in `eobs.payment_number`. Likely different data sources, time periods, or payment number conventions between bank and EOB systems. **Cannot be fixed by code changes.** |
| **Has TRN, EOB exists, amount diff > $5** | ~9 | Payment number matches an EOB, but `abs(txn.amount) - eob.adjusted_amount` exceeds fee tolerance (500¢). Diffs range from $16–$94. Increasing tolerance would be risky (false positives). |
| **No TRN pattern in note** | ~713 | Notes like "MetLife" (no reference) — rely on PayerAmountDateMatcher. |
| **Has TRN, EOB exists, amount match (should've matched)** | 0 | Edge case; none found. |

**Sample TRN→no EOB:**
```
'736706124' | 'HCCLAIMPMT ZP UHCDComm5044 TRN*1*736706124*1470858530\'
'736363822' | 'HCCLAIMPMT PAY PLUS TRN*1*736363822*1351835818\'
'1206746024' | 'HCCLAIMPMT HNB - ECHO TRN*1*1206746024*1341858379\'
```

**Sample TRN + amount mismatch:**
```
pn=CN17425105436265237675273 diff=1600¢ ($16) | txn=-$81 eob=$97
pn=202508040097040 diff=4200¢ ($42) | Delta Dental
pn=825155000434384 diff=3800¢ ($38) | Aetna
```

---

### 3. Payer + Amount + Date Analysis

| Category | Count | Explanation |
|----------|-------|-------------|
| **Payer in note but no EOB with (payer, amount)** | ~571 | Note contains MetLife, Delta, etc., but no EOB exists for that payer + exact amount. Data gap. |
| **Payer+amount match but date outside window** | ~125 | EOB exists for payer+amount, but `received_at` vs `payment_date` exceeds 14-day window. Samples show 169–278 days off — likely wrong candidate (same amount, different payment). |
| **Payer+amount+date match but multiple candidates** | ~1 | Ambiguous; matcher picks closest date at 0.7 confidence. |

**Sample date-window failures:**
```
MetLife $214.00 | txn_date=2025-09-09 eob_date=2025-03-24 days_off=169
MetLife $315.00 | txn_date=2025-09-09 eob_date=2024-12-05 days_off=278
```

---

### 4. Payment Number Format Mismatch

- **Bank TRN:** 1,741 unique payment numbers (lengths: 9, 15, 10 digits common)
- **EOB payment_number:** 3,526 unique
- **Exact overlap:** Only 9

Bank and EOB systems use different payment number conventions. Normalizing (e.g. stripping leading zeros) yielded 0 additional matches.

---

### 5. Amount-Only (Risky)

~325 transactions have a single EOB with the same amount but no payer signal in the note. Matching on amount+date alone would be high-risk (many amount collisions).

---

## Improvements Implemented

### Payer Coverage

Extended `build_payer_note_map_from_db` to include:

| Payer | Note Pattern | EOBs |
|-------|--------------|------|
| Delta Dental | "Delta" | 890 |
| Cigna | "Cigna" | 229 |
| Aetna | "Aetna" | 184 |
| UnitedHealthcare | "UHC" | 299 |
| Anthem Blue Cross Blue Shield | "Anthem" | 275 |
| California Dental / Delta Dental of CA | "CALIFORNIA DENTA" | — |

### Case-Insensitive Payer Matching

Bank notes are often uppercase (`DELTA DENTAL`, `AETNA`). Payer identification is now case-insensitive.

### Date Window

Expanded from 5 to 14 days for PayerAmountDateMatcher to capture more payer+amount+date matches.

### Impact

- **Before:** 2,783 matched (788 via payer_amount_date)
- **After:** 2,839 matched (844 via payer_amount_date)
- **Gain:** +56 matches

---

## Remaining Gaps (Not Fixable by Code)

1. **TRN payment number mismatch (1,677):** Bank and EOB data use different payment number schemes or come from different time periods. Requires data alignment or upstream integration.
2. **No EOB for payer+amount (571):** EOBs simply don't exist for those combinations in the dataset.
3. **Large date gaps (125):** Expanding the window further would increase false matches (same amount, different payments).

---

## Analysis Scripts

- `scripts/analyze_unmatched.py` — Full breakdown of unmatched transactions
- `scripts/analyze_unmatched_v2.py` — Payment number format and payer pattern analysis
