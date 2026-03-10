from .database import db
from .models import (
    EOB,
    BankTransaction,
    Payer,
    ReconciliationMatch,
    TransactionClassification,
)


def init_db():
    """Initialize database tables (idempotent)."""
    db.create_tables(
        [Payer, BankTransaction, EOB, TransactionClassification, ReconciliationMatch],
        safe=True,
    )
