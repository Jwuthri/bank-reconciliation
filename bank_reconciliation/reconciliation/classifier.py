"""Two-stage classifier for bank transactions: rules first, then LLM fallback.

Stage 1 (rules): Fast regex-based pass.  Insurance patterns are checked first;
if none match, noise patterns are checked.  Transactions that hit a rule get a
definitive label immediately.

Stage 2 (LLM): Transactions that fall through all rules as "unknown" are sent
to OpenAI gpt-5-mini in batches for a second opinion.  The LLM receives
few-shot examples of insurance vs. non-insurance notes and returns a boolean.

The LLM stage is **opt-in** — callers must pass ``use_llm=True`` to
``classify_all``.  Without it the behaviour is identical to a pure rule-based
classifier (unknowns default to non-insurance).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Sequence

from bank_reconciliation.db.models import BankTransaction, TransactionClassification

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Rule:
    pattern: re.Pattern[str]
    label: str
    is_insurance: bool


def _ins(pattern: str, label: str) -> _Rule:
    return _Rule(re.compile(pattern, re.IGNORECASE), label, is_insurance=True)


def _noise(pattern: str, label: str) -> _Rule:
    return _Rule(re.compile(pattern, re.IGNORECASE), label, is_insurance=False)


# Order matters: first match wins.
RULES: list[_Rule] = [
    # ---- insurance (positive signals) ----
    _ins(r"HCCLAIMPMT", "HCCLAIMPMT"),
    _ins(r"^MetLife$", "MetLife"),
    _ins(r"CALIFORNIA DENTA", "CALIFORNIA_DENTA"),
    _ins(r"Guardian Life", "Guardian"),
    # ---- noise (negative signals) ----
    _noise(r"BNKCD SETTLE", "card_settlement"),
    _noise(r"Simplifeye", "simplifeye"),
    _noise(r"PAYROLL|TD PAYROLL", "payroll"),
    _noise(r"\brent\b", "rent"),
    _noise(r"PAYMENT TO COMMERCIAL LOAN|LOAN PAYMENT", "loan"),
    _noise(r"SERVICE CHARGE", "service_charge"),
    _noise(r"FeeTransfer", "fee_transfer"),
    _noise(r"HARTFORD", "hartford_insurance"),
    _noise(r"PROTECTIVE LIFE", "protective_life"),
    _noise(r"CHASE CREDIT|CHASE CRD", "chase_credit"),
    _noise(r"\bAMEX\b", "amex"),
    _noise(r"EverBank", "everbank"),
    _noise(r"HENRY SCHEIN", "henry_schein"),
    _noise(r"\bIRS\b", "irs"),
    _noise(r"\bGUSTO\b", "gusto"),
    _noise(r"Wire Out", "wire_out"),
    _noise(r"KAISER", "kaiser"),
    _noise(r"Electronic Payment", "electronic_payment"),
    _noise(r"ADMIN NETWORKS", "admin_networks"),
    _noise(r"DENTU-TEMPS", "dentu_temps"),
    _noise(r"\bANTONOV\b", "antonov"),
    _noise(r"\bKIMBERLY\b", "kimberly"),
    _noise(r"\bTDIC\b", "tdic"),
    _noise(r"\bDMV\b", "dmv"),
    _noise(r"CARD PROCESSING", "card_processing"),
    _noise(r"VENDOR.*SALE", "vendor_sale"),
    _noise(r"Service Charge Rebate", "service_charge_rebate"),
]


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Classification:
    is_insurance: bool
    label: str


# ---------------------------------------------------------------------------
# Stage 1: Rule-based classifier
# ---------------------------------------------------------------------------


def classify_transaction(note: str | None) -> Classification:
    """Classify a single transaction note. Pure function, no DB access."""
    if not note:
        return Classification(is_insurance=False, label="empty_note")

    for rule in RULES:
        if rule.pattern.search(note):
            return Classification(is_insurance=rule.is_insurance, label=rule.label)

    return Classification(is_insurance=False, label="unknown")


# ---------------------------------------------------------------------------
# Stage 2: LLM fallback for "unknown" transactions
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """\
You are a classifier for a dental practice's bank account transactions.
Your job: decide whether a transaction note represents an **insurance payment**
(money coming from an insurance company to pay dental claims) or **not insurance**
(payroll, rent, supplies, card processing, patient payments, fees, etc.).

Respond with ONLY a JSON array of booleans, one per transaction, in the same
order as the input. true = insurance, false = not insurance.

Example input:
["DELTA DENTAL MA PAYMENT 5803916", "Cherry Funding 2267716", "CHECK 5129", "REMOTE DEPOSIT CAPTURE"]

Example output:
[true, false, false, false]

More examples of INSURANCE (true):
- "DELTA DENTAL MA PAYMENT 5803916" — Delta Dental paying a claim
- "AMERITAS LIFE PAYMENT 123456" — Ameritas insurance payment
- "UNITED CONCORDIA DNTL CLAIM" — dental insurance claim payment
- "PRINCIPAL LIFE DENTAL PMT" — Principal insurance payment
- "REMOTE DEPOSIT CAPTURE" with a negative amount could be a scanned insurance check, but without more context default to false

More examples of NOT INSURANCE (false):
- "CHECK 5129" — practice writing a check (outgoing)
- "Cherry Funding 2267716" — patient financing company
- "DEPOSIT" — generic deposit, not identifiable as insurance
- "REMOTE DEPOSIT CAPTURE" — could be anything, not clearly insurance
- "BKCD PROCESSING SETTLEMENT" — card processing settlement
- "RONSMEDICALGASES PURCHASE" — medical supply purchase
- "SMC TAX ECHECK TAX COLL." — tax payment
- "DCM DSO LLC ACCTVERIFY" — account verification, not insurance
- "Remote Deposit Capture Refund - Multi" — refund, not insurance payment\
"""

_LLM_MODEL = "gpt-5-mini"
_LLM_BATCH_SIZE = 40  # notes per API call (fits comfortably in context)
_LLM_MAX_CONCURRENT = 5


async def _call_openai(notes: list[str], client: object) -> list[bool]:
    """Send a batch of notes to OpenAI and return boolean classifications."""
    user_content = json.dumps(notes)
    response = await client.chat.completions.create(  # type: ignore[union-attr]
        model=_LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw = response.choices[0].message.content
    parsed = json.loads(raw)  # type: ignore[arg-type]

    # The model might wrap the array in an object like {"results": [...]}
    if isinstance(parsed, dict):
        parsed = next(v for v in parsed.values() if isinstance(v, list))

    if not isinstance(parsed, list) or len(parsed) != len(notes):
        logger.warning(
            "LLM returned %d results for %d notes; falling back to all-false",
            len(parsed) if isinstance(parsed, list) else -1,
            len(notes),
        )
        return [False] * len(notes)

    return [bool(v) for v in parsed]


async def _classify_unknowns_with_llm(
    unknowns: list[tuple[int, str]],
) -> dict[int, bool]:
    """Classify a list of (txn_id, note) pairs via the OpenAI API.

    Returns a mapping of txn_id -> is_insurance.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.error(
            "openai package not installed. Run: pip install openai"
        )
        return {}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error(
            "OPENAI_API_KEY not set — skipping LLM classification"
        )
        return {}

    client = AsyncOpenAI(api_key=api_key)
    results: dict[int, bool] = {}
    semaphore = asyncio.Semaphore(_LLM_MAX_CONCURRENT)

    async def _process_batch(batch: list[tuple[int, str]]) -> None:
        ids = [b[0] for b in batch]
        notes = [b[1] for b in batch]
        async with semaphore:
            try:
                bools = await _call_openai(notes, client)
                for txn_id, is_ins in zip(ids, bools):
                    results[txn_id] = is_ins
            except Exception:
                logger.exception("LLM batch failed for %d notes", len(notes))

    tasks = []
    for i in range(0, len(unknowns), _LLM_BATCH_SIZE):
        tasks.append(_process_batch(unknowns[i : i + _LLM_BATCH_SIZE]))

    await asyncio.gather(*tasks)
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_all(
    transactions: Sequence[BankTransaction] | None = None,
    *,
    use_llm: bool = False,
    batch_size: int = 500,
) -> dict[str, int]:
    """Classify every bank transaction and persist to TransactionClassification.

    Two-stage pipeline:
      1. Rule-based: instant, covers ~87% of transactions.
      2. LLM (opt-in): sends "unknown" notes to gpt-5-mini for a second opinion.

    Existing classifications are skipped (idempotent).

    Args:
        transactions: Optional explicit list; if *None*, queries all rows.
        use_llm: If True, run unknown transactions through the LLM stage.
                 Requires ``openai`` package and ``OPENAI_API_KEY`` env var.
        batch_size: Insert batch size for bulk writes.

    Returns:
        Summary counts keyed by label.
    """
    if transactions is None:
        transactions = list(BankTransaction.select())

    already_classified: set[int] = {
        row[0]
        for row in TransactionClassification.select(
            TransactionClassification.bank_transaction
        )
        .tuples()
        .iterator()
    }

    rows_to_insert: list[dict] = []
    unknowns: list[tuple[int, str]] = []  # (txn_id, note) for LLM stage
    counts: dict[str, int] = {}

    for txn in transactions:
        if txn.id in already_classified:
            continue

        result = classify_transaction(txn.note)

        if result.label == "unknown" and use_llm and txn.note:
            unknowns.append((txn.id, txn.note))
            continue

        rows_to_insert.append(
            {
                "bank_transaction": txn.id,
                "is_insurance": result.is_insurance,
                "label": result.label,
            }
        )
        counts[result.label] = counts.get(result.label, 0) + 1

    # --- Stage 2: LLM for unknowns ---
    if unknowns:
        logger.info("Sending %d unknown transactions to LLM", len(unknowns))
        llm_results = asyncio.run(_classify_unknowns_with_llm(unknowns))

        for txn_id, note in unknowns:
            is_ins = llm_results.get(txn_id, False)
            label = "llm_insurance" if is_ins else "llm_not_insurance"
            rows_to_insert.append(
                {
                    "bank_transaction": txn_id,
                    "is_insurance": is_ins,
                    "label": label,
                }
            )
            counts[label] = counts.get(label, 0) + 1

    # --- Persist ---
    if rows_to_insert:
        with TransactionClassification._meta.database.atomic():
            for i in range(0, len(rows_to_insert), batch_size):
                TransactionClassification.insert_many(
                    rows_to_insert[i : i + batch_size]
                ).execute()

    logger.info(
        "Classified %d new transactions (%d skipped): %s",
        len(rows_to_insert),
        len(already_classified),
        counts,
    )
    return counts
