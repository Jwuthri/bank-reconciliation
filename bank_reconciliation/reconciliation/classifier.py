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
from typing import Literal, Sequence

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
    _noise(r"Service Charge Rebate", "service_charge_rebate"),
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
]


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Classification:
    is_insurance: bool
    label: str
    confidence: float = 1.0


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

    return Classification(is_insurance=False, label="unknown", confidence=0.0)


# ---------------------------------------------------------------------------
# Stage 2: LLM fallback for "unknown" transactions
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """\
You are a classifier for a dental practice's bank account transactions.
Your job: decide whether a transaction note represents an **insurance payment**
(money coming from an insurance company to pay dental claims) or **not insurance**
(payroll, rent, supplies, card processing, patient payments, fees, etc.).

Respond with ONLY a JSON object: {"insurance": true} or {"insurance": false}.

Examples of INSURANCE (true):
- "DELTA DENTAL MA PAYMENT 5803916" — Delta Dental paying a claim
- "DirPay DELTA DENTAL IL TRN*1*071001733586696*1362612058\\" — direct-pay insurance
- "AMERITAS LIFE PAYMENT 123456" — Ameritas insurance payment
- "UNITED CONCORDIA DNTL CLAIM" — dental insurance claim payment
- "PRINCIPAL LIFE DENTAL PMT" — Principal insurance payment

Examples of NOT INSURANCE (false):
- "CHECK 5129" — practice writing a check (outgoing)
- "Cherry Funding 2267716" — patient financing company
- "DEPOSIT" — generic deposit, not identifiable as insurance
- "REMOTE DEPOSIT CAPTURE" — could be anything, not clearly insurance
- "BKCD PROCESSING SETTLEMENT" — card processing settlement
- "RONSMEDICALGASES PURCHASE" — medical supply purchase
- "SMC TAX ECHECK TAX COLL." — tax payment
- "DCM DSO LLC ACCTVERIFY" — account verification, not insurance
- "Remote Deposit Capture Refund - Multi" — refund, not insurance payment
- "Bill.com DCM DSO LLC" — vendor invoice payment
- "Outgoing Wire Fee" — bank fee
- "GCADMIN NETWO" — admin/network vendor\
"""

_LLM_MODEL = "gpt-5-mini"
_LLM_MAX_CONCURRENT = 8


async def _call_openai_single(
    note: str, client: object
) -> bool:
    """Send a single note to OpenAI and return True if insurance."""
    response = await client.chat.completions.create(  # type: ignore[union-attr]
        model=_LLM_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": note},
        ],
    )
    raw = response.choices[0].message.content
    parsed = json.loads(raw)  # type: ignore[arg-type]

    if isinstance(parsed, dict) and "insurance" in parsed:
        return bool(parsed["insurance"])

    logger.warning("LLM returned unexpected format for %r: %s", note, raw)
    return False


async def _classify_unknowns_with_llm(
    unknowns: list[tuple[int, str]],
) -> dict[int, bool]:
    """Classify a list of (txn_id, note) pairs via the OpenAI API.

    One API call per note, scaled with concurrency.
    Returns a mapping of txn_id -> is_insurance.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.error(
            "openai package not installed. Run: pip install openai"
        )
        return {}

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error(
            "OPENAI_API_KEY not set — add it to .env or export it"
        )
        return {}

    client = AsyncOpenAI(api_key=api_key)
    results: dict[int, bool] = {}
    semaphore = asyncio.Semaphore(_LLM_MAX_CONCURRENT)

    async def _classify_one(txn_id: int, note: str) -> None:
        async with semaphore:
            try:
                results[txn_id] = await _call_openai_single(note, client)
            except Exception:
                logger.exception("LLM call failed for txn %d: %r", txn_id, note)

    await asyncio.gather(*[_classify_one(tid, n) for tid, n in unknowns])
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_all(
    transactions: Sequence[BankTransaction] | None = None,
    *,
    use_llm: bool = False,
    batch_size: int = 500,
    overwrite: bool = False,
    mode: Literal["precision", "recall"] = "precision",
) -> dict[str, int]:
    """Classify every bank transaction and persist to TransactionClassification.

    Two-stage pipeline:
      1. Rule-based: instant, covers ~87% of transactions.
      2. LLM (opt-in): sends "unknown" notes to gpt-5-mini for a second opinion.

    Existing classifications are skipped (idempotent) unless overwrite=True.

    Args:
        transactions: Optional explicit list; if *None*, queries all rows.
        use_llm: If True, run unknown transactions through the LLM stage.
                 Requires ``openai`` package and ``OPENAI_API_KEY`` env var.
        batch_size: Insert batch size for bulk writes.
        overwrite: If True, delete all existing classifications before running.
        mode: "precision" keeps unknowns as not-insurance (confidence=0).
              "recall" marks unknowns as insurance (confidence=0) to avoid
              missing potential insurance transactions.

    Returns:
        Summary counts keyed by label.
    """
    if transactions is None:
        transactions = list(BankTransaction.select())

    if overwrite:
        db = TransactionClassification._meta.database
        db.drop_tables([TransactionClassification])
        db.create_tables([TransactionClassification])
        logger.info("Overwrite: dropped and recreated transaction_classifications")
        already_classified: set[int] = set()
    else:
        already_classified = {
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

        is_insurance = result.is_insurance
        confidence = result.confidence

        if result.label == "unknown" and mode == "recall":
            is_insurance = True

        rows_to_insert.append(
            {
                "bank_transaction": txn.id,
                "is_insurance": is_insurance,
                "label": result.label,
                "confidence": confidence,
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
                    "confidence": 0.5,
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
        "Classified %d new transactions (%d skipped, mode=%s): %s",
        len(rows_to_insert),
        len(already_classified),
        mode,
        counts,
    )
    return counts


# Labels considered insurance (rule-based + LLM)
_INSURANCE_LABELS = frozenset(
    {"HCCLAIMPMT", "MetLife", "CALIFORNIA_DENTA", "Guardian", "llm_insurance"}
)


def _print_dashboard(counts: dict[str, int], *, mode: str = "precision") -> None:
    """Print a Rich dashboard with classification summary."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()
    total = sum(counts.values())
    if total == 0:
        console.print("[dim]No transactions classified.[/]")
        return

    insurance = sum(counts.get(lbl, 0) for lbl in _INSURANCE_LABELS)
    unknown = counts.get("unknown", 0)
    llm_not = counts.get("llm_not_insurance", 0)
    other = total - insurance - unknown - llm_not

    high_conf = total - unknown  # rule-matched + LLM = confidence > 0
    low_conf = unknown           # unknowns = confidence 0

    mode_color = "green" if mode == "recall" else "cyan"
    mode_label = f"[{mode_color} bold]{mode.upper()}[/]"

    # Summary table
    summary = Table(
        title=f"Classification Dashboard  (mode: {mode_label})",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    summary.add_column("Category", style="bold")
    summary.add_column("Count", justify="right")
    summary.add_column("%", justify="right")
    summary.add_column("Bar", ratio=1)

    def _row(cat: str, n: int, style: str = "") -> None:
        pct = n / total * 100 if total else 0
        bar_len = max(0, int(pct / 2))
        bar = "█" * bar_len
        summary.add_row(cat, f"{n:,}", f"{pct:.1f}%", f"[{style}]{bar}[/]")

    _row("Insurance", insurance, "green")
    _row("Unknown", unknown, "yellow")
    _row("LLM (not insurance)", llm_not, "dim")
    _row("Other (noise)", other, "red")
    summary.add_row("", "", "", "", style="dim")
    _row("Total", total, "bold")

    console.print()
    console.print(Panel(summary, border_style="blue"))
    console.print()

    # Confidence breakdown
    conf_table = Table(
        title="Confidence Breakdown",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    conf_table.add_column("Confidence", style="bold")
    conf_table.add_column("Count", justify="right")
    conf_table.add_column("%", justify="right")
    conf_table.add_column("Description")

    high_pct = high_conf / total * 100 if total else 0
    low_pct = low_conf / total * 100 if total else 0
    conf_table.add_row(
        "[green]1.0[/]", f"{high_conf:,}", f"{high_pct:.1f}%",
        "Rule-matched (certain)",
    )
    unknown_desc = (
        "Unknown → treated as insurance" if mode == "recall"
        else "Unknown → treated as NOT insurance"
    )
    conf_table.add_row(
        "[yellow]0.0[/]", f"{low_conf:,}", f"{low_pct:.1f}%",
        unknown_desc,
    )

    console.print(Panel(conf_table, border_style="blue"))
    console.print()

    # Label breakdown table
    breakdown = Table(
        title="By Label",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    breakdown.add_column("Label", style="bold")
    breakdown.add_column("Count", justify="right")
    breakdown.add_column("%", justify="right")
    breakdown.add_column("Confidence", justify="center")

    for label in sorted(counts.keys(), key=lambda k: -counts[k]):
        n = counts[label]
        pct = n / total * 100 if total else 0
        lbl_text = Text(label)
        if label in _INSURANCE_LABELS:
            lbl_text.stylize("green")
        elif label == "unknown":
            lbl_text.stylize("yellow")
        conf_str = "[yellow]0.0[/]" if label == "unknown" else "[green]1.0[/]"
        breakdown.add_row(lbl_text, f"{n:,}", f"{pct:.1f}%", conf_str)

    console.print(Panel(breakdown, border_style="blue"))
    console.print()



def main() -> None:
    """CLI entrypoint: classify all bank transactions and persist to DB."""
    import argparse

    from bank_reconciliation.db.database import db
    from bank_reconciliation.db.init_db import init_db

    parser = argparse.ArgumentParser(
        description="Classify bank transactions (insurance vs not) and persist to DB.",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Run unknowns through the LLM stage (requires OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Insert batch size for bulk writes (default: 500).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing classifications and reclassify all transactions.",
    )
    parser.add_argument(
        "--mode",
        choices=["precision", "recall"],
        default="precision",
        help=(
            "precision: unknowns are NOT insurance (default). "
            "recall: unknowns ARE insurance (to avoid missing any)."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db.connect()
    try:
        init_db()
        counts = classify_all(
            use_llm=args.llm,
            batch_size=args.batch_size,
            overwrite=args.overwrite,
            mode=args.mode,
        )
        _print_dashboard(counts, mode=args.mode)
    finally:
        db.close()


if __name__ == "__main__":
    main()
