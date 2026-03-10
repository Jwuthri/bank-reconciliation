# 🔍 Exploratory Data Analysis — Bank Reconciliation DB

## 📊 Overview

| Table | Rows | Description |
|---|---|---|
| `payers` | 26 | Insurance payer names (Aetna, Delta Dental, MetLife…) |
| `bank_transactions` | 8,611 | Bank account activity over ~1 year |
| `eobs` | 3,526 | Explanation of Benefits records from payer portals |

📅 **Date range**: Sep 9, 2024 → Sep 9, 2025 (both tables)

---

## 🏥 Payers — 26 Insurance Companies

Top payers by EOB volume:

| Payer | EOBs | ACH | CHECK | NON_PAYMENT |
|---|---|---|---|---|
| 🥇 MetLife | 1,014 | 890 | 1 | 123 |
| 🥈 Delta Dental | 890 | 848 | 0 | 42 |
| 🥉 UnitedHealthcare | 299 | 283 | 0 | 16 |
| Anthem BCBS | 275 | 187 | 45 | 43 |
| Cigna | 229 | 79 | 0 | 150 |
| Guardian | 189 | 186 | 1 | 2 |
| Aetna | 184 | 136 | 0 | 48 |
| Beam | 74 | 65 | 0 | 9 |
| GEHA | 73 | 48 | 8 | 17 |
| Others (17 payers) | 299 | — | — | — |

> ⚠️ Payer IDs have gaps (13, 19, 21, 26, 29, 30 are missing) — some were likely deleted. Not a problem, just FYI.

---

## 🏦 Bank Transactions — The Big Surprise

### ⚡ Amounts Are NEGATIVE for Deposits

This is **counterintuitive** but consistent across the entire dataset:

| Sign | Count | % | What They Are |
|---|---|---|---|
| ➖ **Negative** | 6,991 | 81% | Money coming IN — insurance payments, card settlements, etc. |
| ➕ **Positive** | 1,620 | 19% | Money going OUT — payroll, rent, loans, checks, fees |

> 🚨 **Critical for matching**: You must use `ABS(amount)` when comparing bank transactions to EOB `adjusted_amount`.

---

### ➖ Negative Transactions (Deposits) — Breakdown

| Pattern | Count | Avg $ | What It Is | Insurance? |
|---|---|---|---|---|
| `HCCLAIMPMT ...` | 3,736 | $1,744 | ACH insurance claim payments | ✅ Yes |
| `MetLife` | 1,488 | $539 | MetLife payments (name only, no ref) | ✅ Yes |
| `BNKCD SETTLE MERCH DEP` | 1,024 | $3,092 | Credit card processing settlements | ❌ No |
| `Simplifeye TRANSFER` | 239 | $2,975 | Patient payment platform transfers | ❌ No |
| `REMOTE DEPOSIT CAPTURE` | 134 | $3,473 | Scanned check deposits | 🤷 Maybe |
| `DEPOSIT` | 42 | $1,419 | Generic deposits | 🤷 Maybe |
| `Service Charge Rebate` | 24 | $40 | Bank fee rebates | ❌ No |
| Other | 304 | $774 | Misc | 🤷 Mixed |

---

### ➕ Positive Transactions (Outflows) — Breakdown

| Pattern | Count | What It Is | Insurance? |
|---|---|---|---|
| `CHECK ####` | 462 | Checks written by the practice | 🤷 Some |
| `FeeTransfer` | 428 | Processor fee rebates ($0.88–$259) | ❌ No (but related) |
| `PAYROLL` | 175 | John Doe & Jane Doe payroll | ❌ No |
| `CREDIT CARD` (Chase, Amex) | 69 | Credit card auto-payments | ❌ No |
| `CARD PROCESSING` | 55 | Card settlement fees | ❌ No |
| `VENDOR/SALE` | 51 | Dental supply vendors | ❌ No |
| `TAX/PAYROLL SERVICE` | 38 | IRS, Gusto fees | ❌ No |
| `RENT` | 24 | Monthly rent | ❌ No |
| `LOAN PAYMENT` | 24 | Commercial loan payments | ❌ No |
| `CALIFORNIA DENTA` | 12 | Delta Dental of CA | ✅ **Yes!** |
| `Guardian Life` | 2 | Guardian insurance payments | ✅ **Yes!** |
| Other | ~280 | Wire fees, DMV, misc | ❌ No |

> 💡 **Gotcha**: Almost all insurance payments are negative, but **`CALIFORNIA DENTA` (12 txns) and `Guardian Life` (2 txns) are positive**. Don't filter by sign alone!

---

## 📋 EOBs — Payment Types

| Type | Count | Avg Amount | Description |
|---|---|---|---|
| `ACH` | 3,005 | $1,472 | Electronic transfers — **main matching target** |
| `NON_PAYMENT` | 460 | ~$0 | Claim denials/adjustments |
| `CHECK` | 61 | $591 | Paper checks |

### 🚫 NON_PAYMENT EOBs — Mostly Zeros

| Adjusted Amount | Count | Action |
|---|---|---|
| `= 0` | 453 | ❌ Skip — no money to find in the bank |
| `> 0` | 4 | 🤔 Rare edge case (GEHA, MetLife, Humana adjustments) |
| `< 0` | 3 | 🤔 Refunds/corrections (Aetna, GEHA) |

> 💡 Don't flag zero-dollar NON_PAYMENTs as "missing bank transaction" — there's nothing to find.

---

### 🔧 Adjusted vs Payment Amount (17 EOBs differ)

Only **17 out of 3,526 EOBs** have `adjusted_amount ≠ payment_amount`. Examples:

| Payer | Payment $ | Adjusted $ | Diff | What Happened |
|---|---|---|---|---|
| Delta Dental | $53,008.25 | $54,616.75 | +$1,608.50 | Interest/late fee added |
| MetLife | $0.00 | $904.80 | +$904.80 | NON_PAYMENT with actual refund |
| Aetna | $1,556.80 | $1,594.80 | +$38.00 | Small adjustment |
| Guardian | $340.73 | $340.70 | -$0.03 | Rounding |
| GEHA | $0.00 | -$44.00 | -$44.00 | Refund/clawback |

> 💡 Always match on `adjusted_amount`, not `payment_amount`. It's what actually hits the bank.

---

## 🔑 HCCLAIMPMT Notes — The Gold Mine

The `HCCLAIMPMT` prefix = **"Health Care Claim Payment"** via ACH clearinghouse. The note format is:

```
HCCLAIMPMT <PAYER_CODE> TRN*1*<PAYMENT_NUMBER>*<ROUTING_ID>\
```

### 🎯 Payment Number Match

The `<PAYMENT_NUMBER>` in the TRN field **directly matches** the EOB `payment_number` column.

> ✅ **~2,004 confirmed direct matches** — this is the strongest matching signal in the dataset.

### 🏷️ Payer Codes in HCCLAIMPMT Notes

| Code in Note | Maps To | Count |
|---|---|---|
| `ZP UHCDComm5044` | UnitedHealthcare | 604 |
| `HNB - ECHO` | ⚠️ Multiple payers (Aetna, Guardian…) | 684 |
| `PNC-ECHO` | ⚠️ Multiple payers | ~50 |
| `PAY PLUS` | Anthem BCBS, Cigna | 551 |
| `DELTADENTALCA2C` | Delta Dental of CA | 256 |
| `DELTADNTLINS 3C` | Delta Dental Insurance | 100 |
| `DELTADIC-FEDVIP` | Delta Dental FEDVIP | 85 |
| `HUMANA` | Humana Dental | 41 |
| `GEHA` | GEHA | 32 |
| `CIGNA` | Cigna | varies |
| `DDPAR` | Delta Dental (variant) | varies |
| `DENTEGRA` | Dentegra / Ameritas | varies |
| `UMR` | UMR | 6 |
| `ANTHEM` | Anthem | 9 |

> ⚠️ `HNB - ECHO` and `PNC-ECHO` are **clearinghouse IDs**, not payer names. Multiple payers route through them — you **cannot** determine the payer from these codes alone. Use the payment number to match the EOB, then get the payer from there.

---

## 😰 MetLife — The Hard Case

MetLife transactions just say `"MetLife"` — **no reference number, no TRN, nothing**.

| Metric | Value |
|---|---|
| Bank transactions with note `"MetLife"` | 1,488 |
| MetLife ACH EOBs | 890 |
| Ratio | 1.67 txns per EOB 🤔 |

### Matching Strategy for MetLife

Only available signals:
1. **Amount** — exact match of `ABS(bt.amount)` to `e.adjusted_amount`
2. **Date** — within ~2-5 day window

### ⚠️ Ambiguity Problem

There are **duplicate amount+date combos** in MetLife EOBs (e.g., two EOBs for $280.00 on the same date). This means some matches will be ambiguous.

> 💡 ~934 potential matches by amount + date (within 5 days). Disambiguation needed for duplicates.

---

## 📝 CHECK-Type EOBs — Paper Checks

61 EOBs have `payment_type = 'CHECK'`. These should match against:
- `CHECK ####` bank transactions (462 positive outflows — but these are checks *written*, not received)
- `REMOTE DEPOSIT CAPTURE` (134 negative deposits — scanned checks)

| Payer | CHECK EOBs |
|---|---|
| Anthem BCBS | 45 |
| GEHA | 8 |
| BCBS AL | 2 |
| Ameritas Standard | 2 |
| Others | 4 |

> 🤔 The 462 `CHECK ####` positive transactions are likely checks the practice **wrote** (outgoing), not insurance checks received. Insurance checks would appear as `REMOTE DEPOSIT CAPTURE` when scanned.

---

## 🗑️ Noise to Filter Out

These bank transactions are **NOT insurance** and should **never** generate "Missing EOB" tasks:

| Pattern | Count | Why It's Noise |
|---|---|---|
| `PAYROLL` (John Doe, Jane Doe) | 175 | 💰 Employee salaries |
| `rent` | 24 | 🏢 Office rent |
| `PAYMENT TO COMMERCIAL LOAN` | 24 | 🏦 Loan payments |
| `SERVICE CHARGE` | 24 | 💳 Bank fees |
| `BNKCD SETTLE MERCH DEP` | 1,024 | 💳 Credit card processing |
| `Simplifeye TRANSFER` | 239 | 🦷 Patient payment platform |
| `HARTFORD` / `PROTECTIVE LIFE` | 22 | 🛡️ Business insurance premiums |
| `CHASE CREDIT CRD` / `AMEX` | 69 | 💳 Credit card payments |
| `EverBank` | 9 | 🏦 Banking transfers |
| `AR-EFT HENRY SCHEIN` | 13 | 🦷 Dental supply orders |
| `IRS` / `GUSTO` / `TD PAYROLL` | 42 | 📋 Tax & payroll services |
| `Wire Out` | 7 | 🏦 Wire transfers |
| `KAISER GROUP` | 23 | 🏥 Employee health insurance |
| `FeeTransfer` | 428 | 💸 Processor fee rebates (small $) |
| `Electronic Payment Package` | 12 | 🏦 Bank service |
| `ADMIN NETWORKS` / `DENTU-TEMPS` | 42 | 🏪 Vendor payments |

> 🎯 **Bottom line**: Of 8,611 bank transactions, roughly **5,200 are clearly insurance** (HCCLAIMPMT + MetLife), ~1,300 are clearly NOT insurance, and ~2,100 are ambiguous or need classification.

---

## 🧩 Summary of Matching Signals

| Signal | Strength | Available For |
|---|---|---|
| 🟢 Payment number in TRN | **Strongest** | HCCLAIMPMT transactions (~3,736) |
| 🟡 Payer name in note | **Medium** | MetLife (1,488), CALIFORNIA DENTA (12), Guardian (2) |
| 🟡 Amount match (exact) | **Medium** | All, but many collisions |
| 🟡 Date proximity | **Medium** | All, but fuzzy (1-5 day window) |
| 🔴 Payer code in HCCLAIMPMT | **Weak alone** | Helps narrow, but ECHO/PNC serve multiple payers |
| 🔴 Amount with fee tolerance | **Weak** | Only 17 EOBs have adjustments, so mostly exact |

### 🏗️ Suggested Matching Pipeline

```
1. 🎯 EXACT: Payment number found in TRN note → auto-match
2. 🏷️ PAYER + AMOUNT + DATE: Payer name in note + exact amount + date window → auto-match
3. 🔢 AMOUNT + DATE: No payer signal, but amount + date unique → auto-match with lower confidence
4. 🤔 AMBIGUOUS: Multiple candidates → flag for manual review
5. 🚫 FILTER: Non-insurance transactions → exclude from "Missing EOB" tasks
6. ⏰ TIMEOUT: Unmatched after N days → surface as task
```
