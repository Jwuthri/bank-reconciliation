"""Canonical payer-name mappings for bank notes and display.

Single source of truth for:
- Payer DB name prefix → note pattern (for PayerAmountDateMatcher)
- Note pattern → display name (for dashboard)
- HCCLAIMPMT payer codes → display name (for 835-style notes)
"""

# Payer name prefix (from Payer table) → substring to search in bank transaction notes.
# Used by build_payer_note_map_from_db to map payer_id → note pattern.
PAYER_NAME_TO_NOTE_PATTERN: dict[str, str] = {
    "MetLife": "MetLife",
    "Guardian": "Guardian Life",
    "Delta Dental": "CALIFORNIA DENTA",
    "California Dental": "CALIFORNIA DENTA",
}

# Note pattern (substring in bank note) → display name for dashboard.
# Used by _infer_payer_name when note contains the pattern directly.
NOTE_PATTERN_TO_DISPLAY_NAME: dict[str, str] = {
    "MetLife": "MetLife",
    "CALIFORNIA DENTA": "California Dental",
    "Guardian Life": "Guardian",
}

# HCCLAIMPMT payer codes (from 835 TRN segment) → display name.
# Used when note contains "HCCLAIMPMT" and one of these codes.
# None = unknown/echo, do not infer a name.
HCCLAIMPMT_PAYER_CODES: dict[str, str | None] = {
    "UHCDComm": "UnitedHealthcare",
    "PAY PLUS": "Anthem/Cigna",
    "DELTADENTALCA": "Delta Dental",
    "DELTADNTLINS": "Delta Dental",
    "DELTADIC-FEDVIP": "Delta Dental",
    "HUMANA": "Humana",
    "GEHA": "GEHA",
    "CIGNA": "Cigna",
    "ANTHEM": "Anthem",
    "UMR": "UMR",
    "DDPAR": "Delta Dental",
    "DENTEGRA": "Ameritas/Dentegra",
    "HNB - ECHO": None,
    "HNB-ECHO": None,
    "HNBECHO": None,
    "PNC-ECHO": None,
    "PNCECHO": None,
}
