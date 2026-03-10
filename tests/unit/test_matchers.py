"""Tests for PaymentNumberMatcher and PayerAmountDateMatcher.

Pure-function tests using in-memory data — no database access required.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from bank_reconciliation.reconciliation.matchers import (
    MatchResult,
    PayerAmountDateMatcher,
    PaymentNumberMatcher,
    build_payer_note_map_from_db,
    extract_trn_payment_number,
)
from bank_reconciliation.reconciliation.normalize import (
    normalize_note,
    normalize_payment_number,
)


# ---------------------------------------------------------------------------
# TRN extraction
# ---------------------------------------------------------------------------


class TestExtractTrnPaymentNumber:
    @pytest.mark.parametrize(
        "note, expected",
        [
            (
                "HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
                "736886274",
            ),
            (
                "HCCLAIMPMT PAY PLUS TRN*1*736364632*1351835818\\",
                "736364632",
            ),
            (
                "HCCLAIMPMT HNB - ECHO TRN*1*99999*XXXXXXX\\",
                "99999",
            ),
            (
                "HCCLAIMPMT DELTADENTALCA2C TRN*1*55555*DLT\\",
                "55555",
            ),
            (
                "HCCLAIMPMT HUMANA TRN*1*H001*HUM\\",
                "H001",
            ),
        ],
        ids=["uhc", "pay_plus", "echo", "delta_ca", "humana"],
    )
    def test_extracts_payment_number(self, note: str, expected: str):
        assert extract_trn_payment_number(note) == expected

    def test_returns_none_for_no_trn(self):
        assert extract_trn_payment_number("MetLife") is None

    def test_returns_none_for_empty(self):
        assert extract_trn_payment_number("") is None

    def test_returns_none_for_none(self):
        assert extract_trn_payment_number(None) is None

    def test_returns_none_for_malformed_trn(self):
        assert extract_trn_payment_number("HCCLAIMPMT TRN*2*ABC*DEF\\") is None


# ---------------------------------------------------------------------------
# MatchResult dataclass
# ---------------------------------------------------------------------------


class TestMatchResult:
    def test_fields(self):
        r = MatchResult(
            eob_id=1,
            bank_transaction_id=2,
            confidence=1.0,
            match_method="payment_number",
        )
        assert r.eob_id == 1
        assert r.bank_transaction_id == 2
        assert r.confidence == 1.0
        assert r.match_method == "payment_number"

    def test_frozen(self):
        r = MatchResult(
            eob_id=1,
            bank_transaction_id=2,
            confidence=1.0,
            match_method="test",
        )
        with pytest.raises(AttributeError):
            r.confidence = 0.5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers: lightweight stand-ins for DB model objects
# ---------------------------------------------------------------------------


class FakeBankTransaction:
    """Minimal stand-in for BankTransaction with only the fields matchers need."""

    def __init__(self, id: int, amount: int, note: str | None, received_at: datetime):
        self.id = id
        self.amount = amount
        self.note = note
        self.received_at = received_at


class FakeEOB:
    """Minimal stand-in for EOB."""

    def __init__(
        self,
        id: int,
        payment_number: str | None,
        payer_id: int,
        adjusted_amount: int,
        payment_date: datetime,
    ):
        self.id = id
        self.payment_number = payment_number
        self.payer_id = payer_id
        self.adjusted_amount = adjusted_amount
        self.payment_date = payment_date


class FakePayer:
    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name


# ---------------------------------------------------------------------------
# PaymentNumberMatcher
# ---------------------------------------------------------------------------


class TestPaymentNumberMatcher:
    def _make_matcher(self, eobs: list[FakeEOB]) -> PaymentNumberMatcher:
        return PaymentNumberMatcher(eobs)

    def test_exact_match_amount_equal(self):
        eob = FakeEOB(
            id=10,
            payment_number="736886274",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=13,
            amount=-24700,
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])

        assert len(results) == 1
        assert results[0].eob_id == 10
        assert results[0].bank_transaction_id == 13
        assert results[0].confidence == 1.0
        assert results[0].match_method == "payment_number"

    def test_no_match_when_payment_number_not_found(self):
        eob = FakeEOB(
            id=10,
            payment_number="999999999",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=13,
            amount=-24700,
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_no_match_when_no_trn(self):
        eob = FakeEOB(
            id=10,
            payment_number="736886274",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=13,
            amount=-24700,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_confidence_0_9_when_amount_mismatch(self):
        """Payment number matches but amount differs slightly (fee tolerance)."""
        eob = FakeEOB(
            id=10,
            payment_number="736886274",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=13,
            amount=-24500,  # 200 cents off
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])

        assert len(results) == 1
        assert results[0].confidence == 0.9
        assert results[0].match_method == "payment_number"

    def test_no_match_when_amount_too_far(self):
        """Payment number matches but amount is way off — no match."""
        eob = FakeEOB(
            id=10,
            payment_number="736886274",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=13,
            amount=-50000,  # way off
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_multiple_transactions_matched(self):
        eobs = [
            FakeEOB(id=1, payment_number="AAA", payer_id=1, adjusted_amount=100, payment_date=datetime(2025, 1, 1)),
            FakeEOB(id=2, payment_number="BBB", payer_id=1, adjusted_amount=200, payment_date=datetime(2025, 1, 1)),
        ]
        bts = [
            FakeBankTransaction(id=10, amount=-100, note="HCCLAIMPMT X TRN*1*AAA*Y\\", received_at=datetime(2025, 1, 1)),
            FakeBankTransaction(id=11, amount=-200, note="HCCLAIMPMT X TRN*1*BBB*Y\\", received_at=datetime(2025, 1, 1)),
            FakeBankTransaction(id=12, amount=-300, note="HCCLAIMPMT X TRN*1*CCC*Y\\", received_at=datetime(2025, 1, 1)),
        ]
        matcher = self._make_matcher(eobs)
        results = matcher.match(bts)

        assert len(results) == 2
        matched_eob_ids = {r.eob_id for r in results}
        assert matched_eob_ids == {1, 2}

    def test_eob_matched_only_once(self):
        """If two transactions have the same TRN payment number, only the first wins."""
        eob = FakeEOB(id=1, payment_number="AAA", payer_id=1, adjusted_amount=100, payment_date=datetime(2025, 1, 1))
        bts = [
            FakeBankTransaction(id=10, amount=-100, note="HCCLAIMPMT X TRN*1*AAA*Y\\", received_at=datetime(2025, 1, 1)),
            FakeBankTransaction(id=11, amount=-100, note="HCCLAIMPMT Z TRN*1*AAA*Y\\", received_at=datetime(2025, 1, 2)),
        ]
        matcher = self._make_matcher([eob])
        results = matcher.match(bts)

        assert len(results) == 1
        assert results[0].bank_transaction_id == 10

    def test_skips_already_matched_eobs(self):
        """EOBs in the already_matched_eob_ids set are skipped."""
        eob = FakeEOB(id=1, payment_number="AAA", payer_id=1, adjusted_amount=100, payment_date=datetime(2025, 1, 1))
        bt = FakeBankTransaction(id=10, amount=-100, note="HCCLAIMPMT X TRN*1*AAA*Y\\", received_at=datetime(2025, 1, 1))
        matcher = self._make_matcher([eob])
        results = matcher.match([bt], already_matched_eob_ids={1})
        assert len(results) == 0

    def test_skips_already_matched_transactions(self):
        """Transactions in the already_matched_txn_ids set are skipped."""
        eob = FakeEOB(id=1, payment_number="AAA", payer_id=1, adjusted_amount=100, payment_date=datetime(2025, 1, 1))
        bt = FakeBankTransaction(id=10, amount=-100, note="HCCLAIMPMT X TRN*1*AAA*Y\\", received_at=datetime(2025, 1, 1))
        matcher = self._make_matcher([eob])
        results = matcher.match([bt], already_matched_txn_ids={10})
        assert len(results) == 0


# ---------------------------------------------------------------------------
# PayerAmountDateMatcher
# ---------------------------------------------------------------------------


class TestPayerAmountDateMatcher:
    """Tests for matching by payer name + amount + date window."""

    PAYER_NOTE_MAP = {
        3: "MetLife",
        4: "Guardian Life",
        5: "CALIFORNIA DENTA",
    }

    def _make_matcher(
        self,
        eobs: list[FakeEOB],
        payer_note_map: dict[int, str] | None = None,
        date_window_days: int = 5,
    ) -> PayerAmountDateMatcher:
        return PayerAmountDateMatcher(
            eobs,
            payer_note_map=payer_note_map if payer_note_map is not None else self.PAYER_NOTE_MAP,
            date_window_days=date_window_days,
        )

    def test_unique_match(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])

        assert len(results) == 1
        assert results[0].eob_id == 1
        assert results[0].bank_transaction_id == 7
        assert results[0].confidence == 0.85
        assert results[0].match_method == "payer_amount_date"

    def test_no_match_wrong_payer(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=4,  # Guardian
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",  # MetLife note -> payer_id 3
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_no_match_wrong_amount(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=99999,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_no_match_outside_date_window(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 8, 1),  # way before
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_multiple_candidates_picks_closest_date(self):
        eob_far = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 4),
        )
        eob_close = FakeEOB(
            id=2,
            payment_number="P002",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 8),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob_far, eob_close])
        results = matcher.match([bt])

        assert len(results) == 1
        assert results[0].eob_id == 2  # closer date
        assert results[0].confidence == 0.7  # ambiguous

    def test_note_contains_match(self):
        """CALIFORNIA DENTA is a contains-match, not exact."""
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=5,
            adjusted_amount=56656,
            payment_date=datetime(2025, 9, 1),
        )
        bt = FakeBankTransaction(
            id=211,
            amount=56656,
            note="CALIFORNIA DENTA CALDENTAL M121209864679",
            received_at=datetime(2025, 9, 2),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])

        assert len(results) == 1
        assert results[0].eob_id == 1

    def test_guardian_life_contains_match(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=4,
            adjusted_amount=103794,
            payment_date=datetime(2025, 9, 7),
        )
        bt = FakeBankTransaction(
            id=51,
            amount=103794,
            note="Guardian Life ACH Paymnt 000000010106639",
            received_at=datetime(2025, 9, 8),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])

        assert len(results) == 1
        assert results[0].eob_id == 1

    def test_skips_already_matched_eobs(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt], already_matched_eob_ids={1})
        assert len(results) == 0

    def test_skips_already_matched_transactions(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt], already_matched_txn_ids={7})
        assert len(results) == 0

    def test_skips_non_mapped_payer_notes(self):
        """Transactions whose note doesn't match any payer pattern are skipped."""
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = self._make_matcher([eob])
        results = matcher.match([bt])
        assert len(results) == 0

    def test_custom_date_window(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 1),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="MetLife",
            received_at=datetime(2025, 9, 9),
        )
        # 5-day window: no match (8 days apart)
        matcher = self._make_matcher([eob], date_window_days=5)
        assert len(matcher.match([bt])) == 0

        # 10-day window: match
        matcher = self._make_matcher([eob], date_window_days=10)
        assert len(matcher.match([bt])) == 1


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


class TestNormalizeNote:
    def test_none_returns_empty(self):
        assert normalize_note(None) == ""

    def test_empty_returns_empty(self):
        assert normalize_note("") == ""

    def test_whitespace_only_returns_empty(self):
        assert normalize_note("   ") == ""

    def test_strips_and_collapses(self):
        assert normalize_note("  hello   world  ") == "hello world"

    def test_tabs_and_newlines(self):
        assert normalize_note("\thello\n  world\t") == "hello world"


class TestNormalizePaymentNumber:
    def test_none_returns_none(self):
        assert normalize_payment_number(None) is None

    def test_empty_returns_none(self):
        assert normalize_payment_number("") is None

    def test_strips_dashes(self):
        assert normalize_payment_number("736-886-274") == "736886274"

    def test_strips_spaces(self):
        assert normalize_payment_number("736 886 274") == "736886274"

    def test_strips_mixed_punctuation(self):
        assert normalize_payment_number(" 736.886/274 ") == "736886274"

    def test_alphanumeric_preserved(self):
        assert normalize_payment_number("ABC123") == "ABC123"

    def test_only_punctuation_returns_none(self):
        assert normalize_payment_number("---") is None


# ---------------------------------------------------------------------------
# Normalization integration in matchers
# ---------------------------------------------------------------------------


class TestPaymentNumberMatcherNormalization:
    """Ensure PaymentNumberMatcher normalizes both EOB keys and TRN extraction."""

    def test_eob_with_dashes_matches_trn_without(self):
        eob = FakeEOB(
            id=1,
            payment_number="736-886-274",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=10,
            amount=-24700,
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = PaymentNumberMatcher([eob])
        results = matcher.match([bt])
        assert len(results) == 1
        assert results[0].eob_id == 1

    def test_eob_with_spaces_matches_trn_without(self):
        eob = FakeEOB(
            id=1,
            payment_number="736 886 274",
            payer_id=1,
            adjusted_amount=24700,
            payment_date=datetime(2025, 9, 9),
        )
        bt = FakeBankTransaction(
            id=10,
            amount=-24700,
            note="HCCLAIMPMT ZP UHCDComm5044 TRN*1*736886274*1470858530\\",
            received_at=datetime(2025, 9, 9),
        )
        matcher = PaymentNumberMatcher([eob])
        results = matcher.match([bt])
        assert len(results) == 1


class TestPayerAmountDateMatcherNormalization:
    """Ensure PayerAmountDateMatcher normalizes notes before payer lookup."""

    PAYER_NOTE_MAP = {3: "MetLife"}

    def test_extra_whitespace_in_note_still_matches(self):
        eob = FakeEOB(
            id=1,
            payment_number="P001",
            payer_id=3,
            adjusted_amount=24120,
            payment_date=datetime(2025, 9, 5),
        )
        bt = FakeBankTransaction(
            id=7,
            amount=-24120,
            note="  MetLife  ",
            received_at=datetime(2025, 9, 9),
        )
        matcher = PayerAmountDateMatcher(
            [eob], payer_note_map=self.PAYER_NOTE_MAP, date_window_days=5,
        )
        results = matcher.match([bt])
        assert len(results) == 1
        assert results[0].eob_id == 1


class TestBuildPayerNoteMapCaseInsensitive:
    """build_payer_note_map_from_db should match payer names case-insensitively."""

    def test_lowercase_payer_name_matches(self):
        payer = FakePayer(id=10, name="metlife dental")
        result = build_payer_note_map_from_db([payer])
        assert 10 in result
        assert result[10] == "MetLife"

    def test_uppercase_payer_name_matches(self):
        payer = FakePayer(id=11, name="METLIFE DENTAL")
        result = build_payer_note_map_from_db([payer])
        assert 11 in result

    def test_exact_case_still_works(self):
        payer = FakePayer(id=12, name="MetLife")
        result = build_payer_note_map_from_db([payer])
        assert 12 in result
