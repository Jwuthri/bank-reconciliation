#!/usr/bin/env python3
"""Analyze unmatched insurance transactions to find improvement opportunities."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from bank_reconciliation.db.database import db
from bank_reconciliation.db.models import (
    BankTransaction,
    EOB,
    Payer,
    ReconciliationMatch,
    TransactionClassification,
)
from bank_reconciliation.reconciliation.matchers import (
    build_payer_note_map_from_db,
    extract_trn_payment_number,
)

# Broader TRN-like patterns: digits at end, *NUM*, etc.
import re

# Payment number patterns we might be missing
_TRN_ALT_RE = re.compile(r"TRN\*1\*([^*]+)\*")
# Check for numbers that look like payment refs: 6-10 digits, sometimes with * around
_DIGIT_SEQ_RE = re.compile(r"\*?(\d{6,12})\*?")
# Common suffixes in notes
_ECHO_SUFFIX_RE = re.compile(r"\*(\d{4,10})\s*$")  # *8386 at end
_PAYMENT_NUM_IN_NOTE = re.compile(r"(?:#|no\.?|num\.?|ref\.?)\s*(\d{6,12})", re.I)


def main() -> None:
    db.connect()
    try:
        # Get insurance transaction IDs
        insurance_txn_ids = {
            row.bank_transaction_id
            for row in TransactionClassification.select(
                TransactionClassification.bank_transaction
            ).where(TransactionClassification.is_insurance == True)  # noqa: E712
        }

        # Get matched transaction IDs
        matched_txn_ids = set()
        for rm in ReconciliationMatch.select():
            if rm.bank_transaction_id:
                matched_txn_ids.add(rm.bank_transaction_id)

        unmatched_ids = insurance_txn_ids - matched_txn_ids
        unmatched_txns = list(
            BankTransaction.select().where(BankTransaction.id << list(unmatched_ids))
        )

        # Get classifier labels for unmatched (need to join on bank_transaction)
        tc_by_txn = {}
        for tc in TransactionClassification.select().where(
            TransactionClassification.bank_transaction << list(unmatched_ids)
        ):
            tc_by_txn[tc.bank_transaction_id] = tc

        eobs = list(EOB.select())
        payers = {p.id: p for p in Payer.select()}
        payer_note_map = build_payer_note_map_from_db(list(Payer.select()))
        eob_by_payment_num = {e.payment_number: e for e in eobs if e.payment_number}
        eob_by_payer_amount: dict[tuple[int, int], list[EOB]] = defaultdict(list)
        for e in eobs:
            eob_by_payer_amount[(e.payer_id, e.adjusted_amount)].append(e)

        print("=" * 80)
        print(f"UNMATCHED INSURANCE TRANSACTIONS: {len(unmatched_txns)}")
        print("=" * 80)

        # 1. By classifier label
        label_counts = Counter(tc_by_txn[t.id].label for t in unmatched_txns if t.id in tc_by_txn)
        print("\n1. BY CLASSIFIER LABEL (unmatched):")
        for lbl, n in label_counts.most_common():
            print(f"   {lbl}: {n}")

        # 2. Notes with TRN - do we extract? Payment number in EOB?
        trn_extractable = []
        trn_no_eob = []
        trn_amount_mismatch = []
        no_trn = []

        for t in unmatched_txns:
            pn = extract_trn_payment_number(t.note)
            if pn:
                eob = eob_by_payment_num.get(pn)
                if eob is None:
                    trn_no_eob.append((t, pn))
                else:
                    diff = abs(abs(t.amount) - eob.adjusted_amount)
                    if diff > 500:
                        trn_amount_mismatch.append((t, pn, eob, diff))
                    else:
                        trn_extractable.append((t, pn))  # Should have matched - odd
            else:
                no_trn.append(t)

        print("\n2. TRN PAYMENT NUMBER ANALYSIS:")
        print(f"   - Has TRN, EOB exists, amount match (should've matched): {len(trn_extractable)}")
        print(f"   - Has TRN, NO EOB with that payment_number: {len(trn_no_eob)}")
        print(f"   - Has TRN, EOB exists, amount diff > $5: {len(trn_amount_mismatch)}")
        print(f"   - No TRN pattern in note: {len(no_trn)}")

        if trn_no_eob:
            print("\n   Sample TRN→no EOB (payment_num, note snippet):")
            for t, pn in trn_no_eob[:5]:
                print(f"     {pn!r} | {(t.note or '')[:70]!r}")

        if trn_amount_mismatch:
            print("\n   Sample TRN + amount mismatch (diff in cents):")
            for t, pn, eob, diff in trn_amount_mismatch[:5]:
                print(f"     pn={pn} diff={diff}¢ txn_amt={t.amount} eob_adj={eob.adjusted_amount} | {(t.note or '')[:50]!r}")

        # 3. Other payment-number-like patterns in notes (not TRN*1*X*)
        alt_patterns = []
        for t in no_trn:
            note = t.note or ""
            # Look for *DIGITS at end (echo style)
            m = _ECHO_SUFFIX_RE.search(note)
            if m:
                num = m.group(1)
                eob = eob_by_payment_num.get(num)
                if eob:
                    diff = abs(abs(t.amount) - eob.adjusted_amount)
                    if diff <= 500:
                        alt_patterns.append(("echo_suffix", t, num, eob, diff))
            # Look for long digit sequences
            for m in _DIGIT_SEQ_RE.finditer(note):
                num = m.group(1)
                if len(num) >= 6 and num not in (extract_trn_payment_number(note) or ""):
                    eob = eob_by_payment_num.get(num)
                    if eob:
                        diff = abs(abs(t.amount) - eob.adjusted_amount)
                        if diff <= 500:
                            alt_patterns.append(("digit_seq", t, num, eob, diff))
                            break

        print("\n3. ALTERNATIVE PAYMENT NUMBER PATTERNS (could match if we extract):")
        echo_style = [x for x in alt_patterns if x[0] == "echo_suffix"]
        digit_style = [x for x in alt_patterns if x[0] == "digit_seq"]
        print(f"   - *DIGITS at end of note (echo style): {len(echo_style)} potential")
        print(f"   - Other digit sequences in note: {len(digit_style)} potential")
        if echo_style:
            print("   Sample echo-style:")
            for _, t, num, eob, diff in echo_style[:3]:
                print(f"     num={num} diff={diff} | {(t.note or '')[:60]!r}")

        # 4. Payer+amount+date - why didn't we match?
        # PayerAmountDateMatcher needs: note contains payer pattern, (payer_id, amount) in index, date within window
        no_payer_in_note = []
        payer_amount_no_eob = []
        payer_amount_date_fail = []
        payer_amount_multi = []

        for t in no_trn:
            payer_id = None
            for pid, pattern in payer_note_map.items():
                if pattern in (t.note or ""):
                    payer_id = pid
                    break
            if payer_id is None:
                no_payer_in_note.append(t)
                continue

            candidates = eob_by_payer_amount.get((payer_id, abs(t.amount)), [])
            if not candidates:
                payer_amount_no_eob.append((t, payer_id))
                continue

            window = timedelta(days=5)
            in_window = [e for e in candidates if abs(t.received_at - e.payment_date) <= window]
            if not in_window:
                payer_amount_date_fail.append((t, payer_id, candidates))
            elif len(in_window) > 1:
                payer_amount_multi.append((t, payer_id, in_window))
            else:
                pass  # Would have matched

        print("\n4. PAYER+AMOUNT+DATE ANALYSIS (unmatched with payer in note):")
        print(f"   - Payer in note but no EOB with (payer, amount): {len(payer_amount_no_eob)}")
        print(f"   - Payer+amount match but date outside 5-day window: {len(payer_amount_date_fail)}")
        print(f"   - Payer+amount+date match but multiple candidates: {len(payer_amount_multi)}")

        if payer_amount_date_fail:
            print("\n   Sample date-window failures (expand window?):")
            for t, pid, cands in payer_amount_date_fail[:3]:
                payer_name = payers.get(pid, type("P", (), {"name": "?"})()).name
                closest = min(cands, key=lambda e: abs((t.received_at - e.payment_date).days))
                days = abs((t.received_at - closest.payment_date).days)
                print(f"     {payer_name} ${abs(t.amount)/100:.2f} | txn_date={t.received_at.date()} eob_date={closest.payment_date.date()} days_off={days}")

        # 5. Amount-only: how many EOBs have same amount, any payer?
        amount_to_eobs: dict[int, list[EOB]] = defaultdict(list)
        for e in eobs:
            amount_to_eobs[e.adjusted_amount].append(e)

        amount_only_potential = 0
        for t in unmatched_txns:
            amt = abs(t.amount)
            cands = amount_to_eobs.get(amt, [])
            if len(cands) == 1 and t not in [x[0] for x in trn_extractable]:
                amount_only_potential += 1

        print("\n5. AMOUNT-ONLY (single EOB with same amount, no payer in note):")
        print(f"   - Potential matches if we relaxed to amount+date: {amount_only_potential} (risky)")

        # 6. Sample of completely opaque notes (no TRN, no known payer)
        opaque = [
            t for t in no_trn
            if t not in [x[0] for x in payer_amount_no_eob]
            and t not in [x[0] for x in payer_amount_date_fail]
            and t not in [x[0] for x in payer_amount_multi]
        ]
        # Actually: no_payer_in_note are those with no payer. So opaque = no TRN and no payer
        opaque = [t for t in no_trn if t in no_payer_in_note and not any(t == x[0] for x in alt_patterns)]
        print("\n6. OPAQUE NOTES (no TRN, no known payer pattern) - sample:")
        for t in opaque[:10]:
            print(f"   ${abs(t.amount)/100:,.2f} | {(t.note or '')[:80]!r}")

        # 7. Payer coverage - which payers have EOBs but we don't match?
        payer_eob_counts = Counter(e.payer_id for e in eobs)
        print("\n7. EOB PAYER COVERAGE:")
        for pid, count in payer_eob_counts.most_common():
            p = payers.get(pid)
            name = p.name if p else "?"
            in_map = "YES" if pid in payer_note_map else "NO"
            print(f"   {name} (id={pid}): {count} EOBs, in payer_note_map: {in_map}")

        # 8. Check for payers in notes we're not mapping
        note_substrings = Counter()
        for t in unmatched_txns:
            note = (t.note or "").upper()
            for p in payers.values():
                if p.name.upper() in note:
                    note_substrings[p.name] += 1
        print("\n8. PAYER NAMES FOUND IN UNMATCHED NOTES:")
        for name, count in note_substrings.most_common(15):
            pid = next((k for k, v in payers.items() if v.name == name), None)
            in_map = "YES" if pid and pid in payer_note_map else "NO"
            print(f"   {name}: {count} occurrences, in map: {in_map}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
