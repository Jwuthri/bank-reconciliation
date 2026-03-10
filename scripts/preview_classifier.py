#!/usr/bin/env python3
"""Preview the two-stage classifier against real bank transactions.

Usage:
    python -m scripts.preview_classifier                  # 50 unknowns, rules only
    python -m scripts.preview_classifier -n 20            # 20 unknowns
    python -m scripts.preview_classifier --all            # every transaction
    python -m scripts.preview_classifier --llm            # run LLM on unknowns
    python -m scripts.preview_classifier --label payroll  # filter by label
    python -m scripts.preview_classifier --unknown        # only unknowns
    python -m scripts.preview_classifier --insurance      # only insurance
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bank_reconciliation.db.database import db
from bank_reconciliation.db.models import BankTransaction
from bank_reconciliation.reconciliation.classifier import (
    classify_transaction,
)

console = Console()


def _amount_str(cents: int) -> str:
    sign = "" if cents >= 0 else "-"
    return f"{sign}${abs(cents) / 100:,.2f}"


def _label_style(label: str, is_insurance: bool) -> str:
    if is_insurance:
        return "bold green"
    if label == "unknown":
        return "bold yellow"
    return "dim"


def build_detail_table(
    transactions: list[BankTransaction],
    *,
    limit: int | None,
    label_filter: str | None,
    only_unknown: bool,
    only_insurance: bool,
) -> tuple[Table, Counter[str], int, int, list[tuple[int, str]]]:
    """Classify transactions and build a Rich table.

    Returns (table, label_counts, shown, total_matched, visible_unknowns).
    visible_unknowns is a list of (txn_id, note) for unknowns shown in the table.
    """
    table = Table(
        show_header=True,
        header_style="bold cyan",
        title_justify="left",
        expand=True,
    )
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("ID", width=6, justify="right")
    table.add_column("Amount", width=12, justify="right")
    table.add_column("Label", width=24)
    table.add_column("Ins?", width=5, justify="center")
    table.add_column("Note", ratio=1, overflow="ellipsis", no_wrap=True)

    counts: Counter[str] = Counter()
    shown = 0
    matched = 0
    visible_unknowns: list[tuple[int, str]] = []

    for txn in transactions:
        result = classify_transaction(txn.note)
        counts[result.label] += 1

        if label_filter and result.label != label_filter:
            continue
        if only_unknown and result.label != "unknown":
            continue
        if only_insurance and not result.is_insurance:
            continue

        matched += 1
        if limit is not None and shown >= limit:
            continue

        shown += 1
        if result.label == "unknown" and txn.note:
            visible_unknowns.append((txn.id, txn.note))

        icon = "[green]✓[/]" if result.is_insurance else "[red]✗[/]"
        style = _label_style(result.label, result.is_insurance)

        table.add_row(
            str(shown),
            str(txn.id),
            _amount_str(txn.amount),
            Text(result.label, style=style),
            icon,
            (txn.note or "—")[:120],
        )

    return table, counts, shown, matched, visible_unknowns


def build_summary_panel(counts: Counter[str]) -> Panel:
    total = sum(counts.values())
    insurance = sum(v for k, v in counts.items() if k in (
        "HCCLAIMPMT", "MetLife", "CALIFORNIA_DENTA", "Guardian",
    ))
    unknown = counts.get("unknown", 0)
    noise = total - insurance - unknown

    summary = Table.grid(padding=(0, 2))
    summary.add_column(justify="right", style="bold")
    summary.add_column()

    summary.add_row("Total transactions", f"[bold]{total:,}[/]")
    summary.add_row("Insurance (rules)", f"[green]{insurance:,}[/]")
    summary.add_row("Noise (rules)", f"[red]{noise:,}[/]")
    summary.add_row("Unknown", f"[yellow]{unknown:,}[/]")
    summary.add_row("", "")

    top_labels = counts.most_common(15)
    for label, count in top_labels:
        pct = count / total * 100 if total else 0
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        summary.add_row(label, f"{count:>5,}  ({pct:5.1f}%)  [cyan]{bar}[/]")

    return Panel(summary, title="Classification Summary", border_style="blue")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview the classifier against real bank data."
    )
    parser.add_argument(
        "-n", "--limit", type=int, default=50,
        help="Max rows to display (default: 50). Ignored with --all.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show every transaction (no row limit).",
    )
    parser.add_argument(
        "--label", type=str, default=None,
        help="Filter to a specific label (e.g. 'unknown', 'HCCLAIMPMT').",
    )
    parser.add_argument(
        "--unknown", action="store_true",
        help="Shortcut for --label unknown.",
    )
    parser.add_argument(
        "--insurance", action="store_true",
        help="Show only insurance-classified transactions.",
    )
    parser.add_argument(
        "--llm", action="store_true",
        help="Run unknowns through the LLM stage (requires OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Only show the summary panel, skip the detail table.",
    )
    args = parser.parse_args()

    db.connect()
    try:
        transactions = list(BankTransaction.select().order_by(BankTransaction.received_at.desc()))
    finally:
        db.close()

    display_limit = None if args.all else args.limit

    # --- Stage 1: Rules-based classification ---
    table, counts, shown, matched, visible_unknowns = build_detail_table(
        transactions,
        limit=display_limit,
        label_filter=args.label,
        only_unknown=args.unknown,
        only_insurance=args.insurance,
    )

    console.print()
    console.print(build_summary_panel(counts))
    console.print()

    if not args.summary_only:
        filter_desc = ""
        if args.label:
            filter_desc = f" [dim](filter: label={args.label})[/]"
        elif args.unknown:
            filter_desc = " [dim](filter: unknown only)[/]"
        elif args.insurance:
            filter_desc = " [dim](filter: insurance only)[/]"

        if matched > shown:
            console.print(
                f"Showing {shown:,} of {matched:,} matching rows{filter_desc}  "
                f"[dim](use -n or --all to see more)[/]"
            )
        else:
            console.print(f"Showing all {shown:,} matching rows{filter_desc}")

        console.print()
        console.print(table)
        console.print()

    # --- Stage 2: LLM on the unknowns visible in the table ---
    if args.llm:
        _preview_llm(visible_unknowns)


def _preview_llm(unknowns: list[tuple[int, str]]) -> None:
    """Send the given unknowns to the LLM and display results."""
    import asyncio
    import os

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from bank_reconciliation.reconciliation.classifier import (
        _classify_unknowns_with_llm,
    )

    if not unknowns:
        console.print("[green]No unknown transactions in the visible rows.[/]")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]OPENAI_API_KEY not set. Add it to .env or export it.[/]")
        sys.exit(1)

    console.print(
        f"Sending [bold]{len(unknowns):,}[/] unknown transactions to "
        f"[cyan]gpt-5-mini[/]…"
    )

    with console.status("Calling OpenAI…"):
        llm_results = asyncio.run(_classify_unknowns_with_llm(unknowns))

    table = Table(
        show_header=True,
        header_style="bold cyan",
        title="LLM Classification Results",
        expand=True,
    )
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("ID", width=6, justify="right")
    table.add_column("LLM says", width=12, justify="center")
    table.add_column("Note", ratio=1, overflow="ellipsis", no_wrap=True)

    ins_count = 0
    for i, (txn_id, note) in enumerate(unknowns, 1):
        is_ins = llm_results.get(txn_id, False)
        if is_ins:
            ins_count += 1
        icon = "[green bold]INSURANCE[/]" if is_ins else "[dim]not insurance[/]"
        table.add_row(str(i), str(txn_id), icon, (note or "—")[:120])

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"[bold]LLM results:[/] [green]{ins_count}[/] insurance, "
        f"[dim]{len(unknowns) - ins_count}[/] not insurance"
    )
    console.print()


if __name__ == "__main__":
    main()
