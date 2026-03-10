# 🧩 Matchers — How They Work

The matchers pair **bank transactions** with **EOBs** (Explanation of Benefits) so the reconciliation engine knows which deposit corresponds to which insurance payment. Two matchers run in sequence: the high-confidence one first, then the fuzzy one for the leftovers.

---

## 📋 Overview

| Matcher | What it matches on | Confidence | Typical use |
|---------|--------------------|-------------|-------------|
| **PaymentNumberMatcher** | TRN payment number + amount | 1.0 or 0.9 | HCCLAIMPMT transactions (~2,000 matches) |
| **PayerAmountDateMatcher** | Payer name + amount + date window | 0.85 or 0.7 | MetLife, Guardian, California Dental (~900 matches) |

---

## 1️⃣ PaymentNumberMatcher — The Precise One

### What it does

For bank notes that contain a **TRN segment** (e.g. `HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\`), it:

1. **Extracts** the payment number from `TRN*1*<NUM>*…`
2. **Looks up** the EOB with that `payment_number`
3. **Checks** that `|bank_amount|` matches `eob.adjusted_amount` (or is close)

### Confidence levels

| Condition | Confidence |
|-----------|-------------|
| Amount matches exactly | **1.0** ✅ |
| Amount within 500¢ (fee tolerance) | **0.9** ⚠️ |
| Amount too far off | No match ❌ |

### Example

```
Bank note:  "HCCLAIMPMT PAY PLUS TRN*1*736364632*1351835818\"
Amount:     -28,500¢
                    ↓
Extract:    736364632
                    ↓
EOB lookup: payment_number = "736364632", adjusted_amount = 28,500
                    ↓
Match! 🎯 confidence = 1.0
```

### Why it’s reliable

The TRN payment number is a direct reference from the clearinghouse. When it’s present and the amount lines up, the match is very reliable.

---

## 2️⃣ PayerAmountDateMatcher — The Fuzzy One

### What it does

For transactions whose **note** identifies a payer (e.g. `MetLife`, `Guardian Life`, `CALIFORNIA DENTA`), it:

1. **Identifies** the payer from the note (via a configurable `payer_note_map`)
2. **Finds** EOBs for that payer with the same `adjusted_amount` as `|bank_amount|`
3. **Filters** by date: EOB `payment_date` must be within ±5 days of `received_at`
4. **Picks** the best candidate (closest date if there are several)

### Confidence levels

| Condition | Confidence |
|-----------|-------------|
| Exactly one candidate in the date window | **0.85** ✅ |
| Multiple candidates | **0.7** (closest date wins) ⚠️ |

### Payer → note patterns (default)

| Payer ID | Note must contain |
|----------|-------------------|
| 3 | `MetLife` |
| 4 | `Guardian Life` |
| 5 | `CALIFORNIA DENTA` |

### Example

```
Bank note:  "MetLife"
Amount:     -24,120¢
Date:       2025-09-09
                    ↓
Payer:      MetLife (payer_id = 3)
                    ↓
EOBs:       payer=3, adjusted_amount=24,120, date within ±5 days
                    ↓
One match:  EOB id=29, date=2025-09-05
                    ↓
Match! 🎯 confidence = 0.85
```

### Why it’s fuzzy

There’s no direct reference number. We rely on payer + amount + date. Duplicate amounts in the same window can be ambiguous, so confidence is lower.

---

## 🔗 Chaining the Matchers

The engine runs them in order:

1. **PaymentNumberMatcher** — matches HCCLAIMPMT transactions with TRN
2. **PayerAmountDateMatcher** — matches the rest using payer + amount + date

Both accept `already_matched_eob_ids` and `already_matched_txn_ids` so each EOB and transaction is matched at most once.

---

## 📦 MatchResult

Each match produces a `MatchResult`:

```python
MatchResult(
    eob_id=10,
    bank_transaction_id=13,
    confidence=1.0,
    match_method="payment_number",  # or "payer_amount_date"
)
```

These are what the engine persists into `reconciliation_matches`.

---

## 🛠️ Extending

- **New payer patterns**: Add entries to `payer_note_map` (or `DEFAULT_PAYER_NOTE_MAP`).
- **Different date window**: Pass `date_window_days=N` to `PayerAmountDateMatcher`.
- **Different fee tolerance**: Adjust `_FEE_TOLERANCE_CENTS` in `PaymentNumberMatcher` (currently 500¢).
