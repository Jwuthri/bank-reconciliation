# 🏦 Transaction Classifier — How It Works

A two-stage classifier that labels bank transactions as **insurance** or **not insurance** for a dental practice. Fast rules first, smart LLM fallback when needed.

---

## 🎯 What It Does

Given a transaction note (e.g. `"DELTA DENTAL MA PAYMENT 5803916"`), the classifier decides:

- ✅ **Insurance** — money from an insurance company paying dental claims  
- ❌ **Not insurance** — payroll, rent, supplies, card processing, fees, etc.

---

## 🔄 Two-Stage Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Transaction    │ ──► │  Stage 1: Rules │ ──► │  Stage 2: LLM   │
│  (note text)    │     │  (regex match)  │     │  (opt-in)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                         │
                               ▼                         ▼
                        ~87% classified            unknowns only
                        (instant)                  (API call)
```

### Stage 1: Rule-Based (Always On) ⚡

- **Regex patterns** run in order — first match wins
- **Insurance rules** first (positive signals): `HCCLAIMPMT`, `MetLife`, `Guardian`, etc.
- **Noise rules** next (negative signals): payroll, rent, card settlement, fees, etc.
- **Result**: definitive label + `confidence=1.0` — no DB, no API, pure function

### Stage 2: LLM Fallback (Opt-In) 🤖

- Only runs when `use_llm=True` and the transaction is still **unknown**
- Sends note text to **OpenAI gpt-5-mini** with few-shot examples
- Returns `{"insurance": true}` or `{"insurance": false}`
- **Labels**: `llm_insurance` or `llm_not_insurance` with `confidence=0.5`
- Requires: `openai` package + `OPENAI_API_KEY` in env

---

## 📋 Rule Order Matters

Rules are evaluated **top to bottom**. Insurance patterns are checked first; if none match, noise patterns run. A transaction that hits a rule gets a definitive label immediately and never reaches the LLM.

| Type      | Examples                                      |
|-----------|-----------------------------------------------|
| Insurance | `HCCLAIMPMT`, `MetLife`, `Guardian`, `CALIFORNIA DENTA` |
| Noise     | `PAYROLL`, `rent`, `SERVICE CHARGE`, `CHASE CREDIT`, `GUSTO`, etc. |

---

## 🎚️ Modes: Precision vs Recall

When a transaction is **unknown** (no rule matched, no LLM):

| Mode        | Unknowns treated as | Use case                          |
|-------------|---------------------|-----------------------------------|
| **precision** (default) | NOT insurance       | Avoid false positives, conservative |
| **recall**   | Insurance           | Don’t miss potential insurance txns |

---

## 🔧 Public API

### `classify_transaction(note: str | None) -> Classification`

Pure function — no DB, no API. Returns:

```python
Classification(is_insurance=bool, label=str, confidence=float)
```

### `classify_all(...) -> dict[str, int]`

Batch classify and persist to `TransactionClassification`:

- `transactions` — optional list; if `None`, loads all from DB
- `use_llm` — run unknowns through the LLM stage
- `batch_size` — bulk insert size (default 500)
- `overwrite` — drop and recreate classifications before running
- `mode` — `"precision"` or `"recall"`

Returns a summary dict: `{label: count}`.

---

## 🖥️ CLI

```bash
python -m bank_reconciliation.reconciliation.classifier [options]
```

| Flag           | Description                                      |
|----------------|--------------------------------------------------|
| `--llm`        | Run unknowns through the LLM                     |
| `--batch-size` | Insert batch size (default: 500)                 |
| `--overwrite`  | Reclassify everything from scratch               |
| `--mode`       | `precision` or `recall`                          |

---

## 📊 Labels at a Glance

| Label              | Meaning                          | Confidence |
|--------------------|----------------------------------|------------|
| `HCCLAIMPMT`, `MetLife`, `Guardian`, `CALIFORNIA_DENTA` | Rule-matched insurance | 1.0 |
| `llm_insurance`    | LLM said insurance               | 0.5        |
| `card_settlement`, `payroll`, `rent`, etc. | Rule-matched noise | 1.0 |
| `llm_not_insurance`| LLM said not insurance           | 0.5        |
| `unknown`          | No rule, no LLM (mode decides)    | 0.0        |

---

## ✨ TL;DR

1. **Rules first** — fast, deterministic, covers most transactions  
2. **LLM optional** — for unknowns when you want a second opinion  
3. **Idempotent** — skips already-classified unless `overwrite=True`  
4. **Mode** — precision = conservative, recall = catch-all for unknowns  
