"""CLI for reconciliation engine operations."""
import argparse
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table

from .reconciliation import ReconciliationEngine
from .reconciliation.dummy_engine import DummyReconciliationEngine


def format_currency(cents: int | None) -> str:
    if cents is None:
        return "N/A"
    return f"${cents / 100:,.2f}"


def format_date(dt: datetime) -> str:
    """Format datetime."""
    return dt.strftime("%Y-%m-%d")


def list_payments(engine: ReconciliationEngine, page: int, page_size: int) -> None:
    """List dashboard payments."""
    result = engine.get_dashboard_payments(page=page - 1, page_size=page_size)

    console = Console()
    table = Table(title=f"Payments (Page {page} of {result.total_pages})")

    table.add_column("Date")
    table.add_column("Payer", style="green")
    table.add_column("Payment #", style="magenta")
    table.add_column("Amount", style="yellow")
    table.add_column("Txn", style="cyan")
    table.add_column("EOB", style="cyan")

    for payment in result.items:
        table.add_row(
            format_date(payment.date),
            payment.payer_name or "N/A",
            payment.payment_number or "N/A",
            format_currency(payment.adjusted_amount),
            payment.bank_transaction_status,
            payment.eob_status,
        )

    console.print(table)
    console.print(
        f"\nShowing {len(result.items)} of {result.total_count} total payments"
    )


def list_missing_transactions(
    engine: ReconciliationEngine, page: int, page_size: int
) -> None:
    """List EOBs missing bank transactions."""
    result = engine.get_missing_bank_transactions(page=page - 1, page_size=page_size)

    console = Console()
    table = Table(
        title=f"EOBs Missing Transactions (Page {page} of {result.total_pages})"
    )

    table.add_column("EOB ID", style="cyan")
    table.add_column("Payment #", style="magenta")
    table.add_column("Payer", style="green")
    table.add_column("Amount", style="yellow")
    table.add_column("Type")

    for task in result.items:
        table.add_row(
            str(task.eob_id),
            task.payment_number,
            task.payer_name,
            format_currency(task.adjusted_amount),
            task.payment_type,
        )

    console.print(table)
    console.print(f"\nShowing {len(result.items)} of {result.total_count} total tasks")


def list_missing_payment_eobs(
    engine: ReconciliationEngine, page: int, page_size: int
) -> None:
    """List transactions missing EOBs."""
    result = engine.get_missing_payment_eobs(page=page - 1, page_size=page_size)

    console = Console()
    table = Table(
        title=f"Transactions Missing EOBs (Page {page} of {result.total_pages})"
    )

    table.add_column("Txn ID", style="cyan")
    table.add_column("Payment #", style="magenta")
    table.add_column("Payer", style="green")
    table.add_column("Amount", style="yellow")
    table.add_column("Date")

    for task in result.items:
        table.add_row(
            str(task.transaction_id),
            task.payment_number or "N/A",
            task.payer_name or "N/A",
            format_currency(task.amount),
            format_date(task.received_at),
        )

    console.print(table)
    console.print(f"\nShowing {len(result.items)} of {result.total_count} total tasks")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bank Reconciliation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list:payments command
    payments_parser = subparsers.add_parser(
        "list:payments", help="List dashboard EOBs"
    )
    payments_parser.add_argument(
        "--page", type=int, default=1, help="Page number (default: 1)"
    )
    payments_parser.add_argument(
        "--page-size", type=int, default=20, help="Items per page (default: 20)"
    )

    # list:missing-transactions command
    missing_txn_parser = subparsers.add_parser(
        "list:missing-transactions", help="List EOBs missing bank transactions"
    )
    missing_txn_parser.add_argument(
        "--page", type=int, default=1, help="Page number (default: 1)"
    )
    missing_txn_parser.add_argument(
        "--page-size", type=int, default=20, help="Items per page (default: 20)"
    )

    # list:missing-payment-eob command
    missing_eob_parser = subparsers.add_parser(
        "list:missing-payment-eob", help="List missing payment EOBs"
    )
    missing_eob_parser.add_argument(
        "--page", type=int, default=1, help="Page number (default: 1)"
    )
    missing_eob_parser.add_argument(
        "--page-size", type=int, default=20, help="Items per page (default: 20)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize engine
    engine = DummyReconciliationEngine()

    # Route to handler
    if args.command == "list:payments":
        list_payments(engine, args.page, args.page_size)
    elif args.command == "list:missing-transactions":
        list_missing_transactions(engine, args.page, args.page_size)
    elif args.command == "list:missing-payment-eob":
        list_missing_payment_eobs(engine, args.page, args.page_size)


if __name__ == "__main__":
    main()
