from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

from .database import db


class BaseModel(Model):
    class Meta:
        database = db


class Payer(BaseModel):
    id = AutoField(primary_key=True)
    name = CharField()

    class Meta:
        table_name = "payers"


class BankTransaction(BaseModel):
    id = AutoField(primary_key=True)
    amount = IntegerField()  # cents
    note = TextField(null=True)
    received_at = DateTimeField()

    class Meta:
        table_name = "bank_transactions"


class EOB(BaseModel):
    id = AutoField(primary_key=True)
    payment_number = CharField(null=True)
    payer = ForeignKeyField(Payer, backref="eobs")
    payment_amount = IntegerField()  # cents
    adjusted_amount = IntegerField()  # cents
    payment_type = CharField()  # ACH, CHECK, VCC, NON_PAYMENT
    payment_date = DateTimeField()

    class Meta:
        table_name = "eobs"


class TransactionClassification(BaseModel):
    id = AutoField(primary_key=True)
    bank_transaction = ForeignKeyField(
        BankTransaction, unique=True, backref="classification"
    )
    is_insurance = BooleanField()
    label = CharField(null=True)  # e.g. "HCCLAIMPMT", "MetLife", "noise"
    confidence = FloatField(default=1.0)  # 0.0–1.0

    class Meta:
        table_name = "transaction_classifications"


class ReconciliationMatch(BaseModel):
    id = AutoField(primary_key=True)
    eob = ForeignKeyField(EOB, unique=True, backref="match")
    bank_transaction = ForeignKeyField(
        BankTransaction, null=True, backref="matches"
    )
    confidence = FloatField()  # 0.0–1.0
    match_method = CharField()  # "payment_number", "payer_amount_date", etc.
    matched_at = DateTimeField()

    class Meta:
        table_name = "reconciliation_matches"
