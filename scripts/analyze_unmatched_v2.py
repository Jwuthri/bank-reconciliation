#!/usr/bin/env python3
"""Deeper analysis: payment number formats, payer patterns, EOB vs bank note alignment."""

from __future__ import annotations

from collections import Counter, defaultdict

from bank_reconciliation.db.database import db
from bank_reconciliation.db.models import (
    BankTransaction,
    EOB,
    Payer,
    ReconciliationMatch,
    TransactionClassification,
)
from bank_reconciliation.reconciliation.matchers import extract_trn_payment_number

import re


def main() -> None:
    db.connect()
    try:
        insurance_txn_ids = {
            row.bank_transaction_id
            for row in TransactionClassification.select(
                TransactionClassification.bank_transaction_id
            ).where(TransactionClassification.is_insurance == True)  # noqa: E712
        }

        matched_txn_ids = {
            rm.bank_transaction_id
            for rm in ReconciliationMatch.select()
            if rm.bank_transaction_id
        }
        unmatched_ids = insurance_txn_ids - matched_txn_ids
        unmatched_txns = list(
            BankTransaction.select().where(BankTransaction.id << list(unmatched_ids))
        )

        tc_by_txn = {}
        for tc in TransactionClassification.select().where(
            TransactionClassification.bank_transaction << list(unmatched_ids)
        ):
            tc_by_txn[tc.bank_transaction_id] = tc

        eobs = list(EOB.select())
        payers = {p.id: p for p in Payer.select()}
        eob_by_payment_num = {e.payment_number: e for e in eobs if e.payment_number}
        eob_payment_num_lengths = Counter(len(str(pn)) for pn in eob_by_payment_num if pn)
        bank_trn_lengths = Counter()

        # Payment numbers in bank notes (TRN) vs EOB
        trn_in_bank = set()
        for t in unmatched_txns:
            pn = extract_trn_payment_number(t.note)
            if pn:
                trn_in_bank.add(pn)
                bank_trn_lengths[len(pn)] += 1

        overlap = trn_in_bank & set(eob_by_payment_num.keys())
        only_bank = trn_in_bank - set(eob_by_payment_num.keys())
        only_eob = set(eob_by_payment_num.keys()) - trn_in_bank

        print("=" * 80)
        print("PAYMENT NUMBER FORMAT ANALYSIS")
        print("=" * 80)
        print(f"\nBank TRN payment numbers: {len(trn_in_bank)} unique")
        print(f"EOB payment_number: {len(eob_by_payment_num)} unique")
        print(f"Overlap (exact match): {len(overlap)}")
        print(f"Only in bank (no EOB): {len(only_bank)}")
        print(f"Only in EOB (no bank TRN): {len(only_eob)}")

        print("\nBank TRN length distribution:", dict(bank_trn_lengths.most_common(10)))
        print("EOB payment_number length distribution:", dict(eob_payment_num_lengths.most_common(10)))

        # Try suffix matching: does EOB end with bank TRN or vice versa?
        suffix_matches = 0
        prefix_matches = 0
        sample_suffix = []
        for pn in list(only_bank)[:500]:
            for eob_pn in list(only_eob)[:2000]:  # sample
                if eob_pn and pn:
                    if eob_pn.endswith(pn) or pn.endswith(eob_pn):
                        suffix_matches += 1
                        if len(sample_suffix) < 5:
                            sample_suffix.append((pn, eob_pn))
                        break
                if eob_pn and pn and (eob_pn.startswith(pn) or pn.startswith(eob_pn)):
                    prefix_matches += 1
                    break

        # Better: for each bank TRN, check if any EOB payment_number contains it or is contained
        contains_count = 0
        contained_count = 0
        samples_contained = []
        for t in unmatched_txns[:500]:
            pn = extract_trn_payment_number(t.note)
            if not pn:
                continue
            for eob_pn, eob in eob_by_payment_num.items():
                if not eob_pn:
                    continue
                if pn in eob_pn:
                    contains_count += 1
                    if len(samples_contained) < 3:
                        samples_contained.append((pn, eob_pn, t.amount, eob.adjusted_amount))
                    break
                if eob_pn in pn:
                    contained_count += 1
                    break

        print("\nPartial match (bank TRN in EOB payment_number):", contains_count)
        print("Partial match (EOB payment_number in bank TRN):", contained_count)
        if samples_contained:
            print("Samples (bank_trn, eob_pn, txn_amt, eob_amt):", samples_contained[:3])

        # EOB payment_number format samples
        print("\nEOB payment_number samples (first 15):")
        for i, (pn, eob) in enumerate(list(eob_by_payment_num.items())[:15]):
            print(f"  {pn!r}")

        print("\nBank TRN samples (from unmatched, first 15):")
        seen = set()
        for t in unmatched_txns:
            pn = extract_trn_payment_number(t.note)
            if pn and pn not in seen:
                seen.add(pn)
                print(f"  {pn!r} | {(t.note or '')[:50]!r}")
                if len(seen) >= 15:
                    break

        # Payer patterns in notes - what do Delta Dental, Aetna, Cigna notes look like?
        print("\n" + "=" * 80)
        print("PAYER PATTERNS IN UNMATCHED NOTES")
        print("=" * 80)

        payer_keywords = ["Delta", "Aetna", "Cigna", "United", "Anthem", "UHC", "GEHA", "UMR"]
        for kw in payer_keywords:
            matches = [(t, tc_by_txn.get(t.id)) for t in unmatched_txns if kw.lower() in (t.note or "").lower()]
            if matches:
                print(f"\n'{kw}' in note: {len(matches)} unmatched")
                for t, tc in matches[:3]:
                    lbl = tc.label if tc else "?"
                    print(f"  [{lbl}] ${abs(t.amount)/100:.2f} | {(t.note or '')[:75]!r}")

        # What payers do we need to add? Map payer name -> possible note patterns
        print("\n" + "=" * 80)
        print("RECOMMENDED PAYER_NOTE_MAP ADDITIONS")
        print("=" * 80)

        # From section 8: Delta Dental 195, Aetna 95, Cigna 90
        # Get payer IDs for these
        payers_by_name = {p.name.lower(): p for p in payers.values()}
        for name in ["Delta Dental", "Aetna", "Cigna", "UnitedHealthcare", "Anthem Blue Cross Blue Shield"]:
            p = payers_by_name.get(name.lower()) or payers_by_name.get(name.split()[0].lower() + " " + name.split()[-1].lower() if " " in name else name.lower())
            if not p:
                for k, v in payers_by_name.items():
                    if name.split()[0].lower() in k:
                        p = v
                        break
            if p:
                eob_count = sum(1 for e in eobs if e.payer_id == p.id)
                print(f"  {p.id}: \"{p.name}\" — {eob_count} EOBs")
                # Find a pattern that appears in notes
                pattern_candidates = [p.name, p.name.split()[0], p.name.replace(" ", "")]
                print(f"    Pattern candidates: {pattern_candidates}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
