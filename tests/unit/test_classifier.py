"""Tests for the rule-based transaction classifier (Stage 1).

These are pure-function tests — no database or network access required.
"""

import pytest

from bank_reconciliation.reconciliation.classifier import (
    Classification,
    classify_transaction,
)


# ---------------------------------------------------------------------------
# Insurance patterns
# ---------------------------------------------------------------------------


class TestInsuranceRules:
    """Transactions that should be classified as insurance."""

    @pytest.mark.parametrize(
        "note, expected_label",
        [
            ("HCCLAIMPMT ZP UHCDComm5044 TRN*1*12345*1234567890\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT HNB - ECHO TRN*1*99999*XXXXXXX\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT PAY PLUS TRN*1*ABC123*ROUTE\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT DELTADENTALCA2C TRN*1*55555*DLT\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT HUMANA TRN*1*H001*HUM\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT GEHA TRN*1*G001*GEHA\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT CIGNA TRN*1*C001*CIG\\", "HCCLAIMPMT"),
            ("HCCLAIMPMT PNC-ECHO TRN*1*P001*PNC\\", "HCCLAIMPMT"),
        ],
        ids=[
            "uhc",
            "echo_clearinghouse",
            "pay_plus",
            "delta_dental_ca",
            "humana",
            "geha",
            "cigna",
            "pnc_echo",
        ],
    )
    def test_hcclaimpmt_variants(self, note: str, expected_label: str):
        result = classify_transaction(note)
        assert result.is_insurance is True
        assert result.label == expected_label
        assert result.confidence == 1.0

    def test_metlife_exact(self):
        result = classify_transaction("MetLife")
        assert result == Classification(is_insurance=True, label="MetLife")

    def test_metlife_must_be_exact(self):
        """MetLife rule is anchored — partial matches should NOT fire."""
        assert classify_transaction("MetLife Insurance Co").is_insurance is False
        assert classify_transaction("Some MetLife thing").is_insurance is False

    @pytest.mark.parametrize(
        "note",
        [
            "CALIFORNIA DENTA",
            "CALIFORNIA DENTAL ASSOC",
            "CALIFORNIA DENTA 12345",
        ],
    )
    def test_california_dental(self, note: str):
        result = classify_transaction(note)
        assert result == Classification(
            is_insurance=True, label="CALIFORNIA_DENTA"
        )

    @pytest.mark.parametrize("note", ["Guardian Life", "Guardian Life Ins"])
    def test_guardian_life(self, note: str):
        result = classify_transaction(note)
        assert result == Classification(is_insurance=True, label="Guardian")


# ---------------------------------------------------------------------------
# Noise patterns
# ---------------------------------------------------------------------------


class TestNoiseRules:
    """Transactions that should be classified as noise (not insurance)."""

    @pytest.mark.parametrize(
        "note, expected_label",
        [
            ("BNKCD SETTLE MERCH DEP", "card_settlement"),
            ("BNKCD SETTLE 12345", "card_settlement"),
            ("Simplifeye TRANSFER", "simplifeye"),
            ("Simplifeye", "simplifeye"),
            ("PAYROLL John Doe", "payroll"),
            ("PAYROLL Jane Doe", "payroll"),
            ("TD PAYROLL SERVICE", "payroll"),
            ("Monthly rent payment", "rent"),
            ("rent", "rent"),
            ("PAYMENT TO COMMERCIAL LOAN", "loan"),
            ("LOAN PAYMENT 12345", "loan"),
            ("SERVICE CHARGE", "service_charge"),
            ("SERVICE CHARGE PERIOD 01", "service_charge"),
            ("FeeTransfer", "fee_transfer"),
            ("FeeTransfer 0.88", "fee_transfer"),
            ("HARTFORD premium", "hartford_insurance"),
            ("HARTFORD", "hartford_insurance"),
            ("PROTECTIVE LIFE", "protective_life"),
            ("PROTECTIVE LIFE INS", "protective_life"),
            ("CHASE CREDIT CRD AUTOPAY", "chase_credit"),
            ("CHASE CRD 1234", "chase_credit"),
            ("AMEX payment", "amex"),
            ("AMEX", "amex"),
            ("EverBank transfer", "everbank"),
            ("EverBank", "everbank"),
            ("AR-EFT HENRY SCHEIN", "henry_schein"),
            ("HENRY SCHEIN DENTAL", "henry_schein"),
            ("IRS USATAXPYMT", "irs"),
            ("GUSTO fee", "gusto"),
            ("GUSTO", "gusto"),
            ("Wire Out 1234", "wire_out"),
            ("Wire Out", "wire_out"),
            ("KAISER GROUP", "kaiser"),
            ("KAISER", "kaiser"),
            ("Electronic Payment Package", "electronic_payment"),
            ("Electronic Payment", "electronic_payment"),
            ("ADMIN NETWORKS", "admin_networks"),
            ("ADMIN NETWORKS INC", "admin_networks"),
            ("DENTU-TEMPS", "dentu_temps"),
            ("DENTU-TEMPS INC", "dentu_temps"),
            ("ANTONOV", "antonov"),
            ("KIMBERLY", "kimberly"),
            ("TDIC premium", "tdic"),
            ("DMV renewal", "dmv"),
            ("CARD PROCESSING FEE", "card_processing"),
            ("VENDOR/SALE DENTAL SUPPLY", "vendor_sale"),
            ("Service Charge Rebate", "service_charge_rebate"),
        ],
    )
    def test_noise_patterns(self, note: str, expected_label: str):
        result = classify_transaction(note)
        assert result.is_insurance is False, (
            f"Expected noise for {note!r}, got insurance"
        )
        assert result.label == expected_label
        assert result.confidence == 1.0

    def test_rent_word_boundary(self):
        """'rent' should match as a word, not as a substring."""
        assert classify_transaction("rent").label == "rent"
        assert classify_transaction("Office rent").label == "rent"
        # "parent" contains "rent" but shouldn't match
        assert classify_transaction("parent company").label != "rent"

    def test_amex_word_boundary(self):
        assert classify_transaction("AMEX").label == "amex"
        # Shouldn't match inside another word
        assert classify_transaction("EXAMEX").label != "amex"


# ---------------------------------------------------------------------------
# Edge cases & unknowns
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_none_note(self):
        result = classify_transaction(None)
        assert result == Classification(is_insurance=False, label="empty_note")
        assert result.confidence == 1.0

    def test_empty_string(self):
        result = classify_transaction("")
        assert result == Classification(is_insurance=False, label="empty_note")
        assert result.confidence == 1.0

    @pytest.mark.parametrize(
        "note",
        [
            "DEPOSIT",
            "DELTA DENTAL MA PAYMENT 5803916",
            "RONSMEDICALGASES PURCHASE JOHN DOE PE",
            "DCM DSO LLC ACCTVERIFY 026EYHFXQ1I57H3",
            "69199 JANE DOE ACCTVERIFY 14053751",
        ],
    )
    def test_unknown_defaults_to_not_insurance(self, note: str):
        result = classify_transaction(note)
        assert result.is_insurance is False
        assert result.label == "unknown"
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Rule ordering / priority
# ---------------------------------------------------------------------------


class TestRulePriority:
    def test_insurance_checked_before_noise(self):
        """If a note somehow matches both an insurance and noise pattern,
        insurance should win because insurance rules come first."""
        result = classify_transaction("HCCLAIMPMT")
        assert result.is_insurance is True

    def test_first_noise_rule_wins(self):
        """Among noise rules, the first match wins."""
        note = "PAYROLL SERVICE CHARGE"
        result = classify_transaction(note)
        assert result.label == "payroll"

    def test_case_insensitivity(self):
        assert classify_transaction("hcclaimpmt something").is_insurance is True
        assert classify_transaction("simplifeye transfer").is_insurance is False
        assert classify_transaction("feetransfer").is_insurance is False
        assert classify_transaction("wire out").is_insurance is False


# ---------------------------------------------------------------------------
# Classification dataclass
# ---------------------------------------------------------------------------


class TestClassificationDataclass:
    def test_frozen(self):
        c = Classification(is_insurance=True, label="test")
        with pytest.raises(AttributeError):
            c.is_insurance = False  # type: ignore[misc]

    def test_equality(self):
        a = Classification(is_insurance=True, label="x")
        b = Classification(is_insurance=True, label="x")
        assert a == b

    def test_inequality(self):
        a = Classification(is_insurance=True, label="x")
        b = Classification(is_insurance=False, label="x")
        assert a != b

    def test_confidence_default(self):
        c = Classification(is_insurance=True, label="test")
        assert c.confidence == 1.0

    def test_confidence_explicit(self):
        c = Classification(is_insurance=False, label="unknown", confidence=0.0)
        assert c.confidence == 0.0

    def test_inequality_by_confidence(self):
        a = Classification(is_insurance=False, label="unknown", confidence=0.0)
        b = Classification(is_insurance=False, label="unknown", confidence=1.0)
        assert a != b


# ---------------------------------------------------------------------------
# Confidence values
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_rule_match_has_full_confidence(self):
        result = classify_transaction("HCCLAIMPMT something")
        assert result.confidence == 1.0

    def test_noise_match_has_full_confidence(self):
        result = classify_transaction("PAYROLL John Doe")
        assert result.confidence == 1.0

    def test_empty_note_has_full_confidence(self):
        result = classify_transaction(None)
        assert result.confidence == 1.0

    def test_unknown_has_zero_confidence(self):
        result = classify_transaction("DEPOSIT")
        assert result.confidence == 0.0

    def test_unknown_has_zero_confidence_various(self):
        for note in ["DEPOSIT", "RONSMEDICALGASES PURCHASE", "DCM DSO LLC ACCTVERIFY"]:
            result = classify_transaction(note)
            assert result.label == "unknown"
            assert result.confidence == 0.0
