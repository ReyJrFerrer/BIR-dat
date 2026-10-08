"""Documented and provisional rules for a source-preserving validation candidate.

See docs/mapping-policy.md for evidence and the limits of this profile.
"""

from string import ascii_uppercase
from unicodedata import normalize

EMPLOYMENT_CODES = frozenset({"R", "C", "CP", "S", "P", "AL"})
SEPARATION_CODES = frozenset({"", "NA", "T", "TR", "R", "D"})
REGION_CODES = frozenset(
    {
        "NCR",
        "CAR",
        "I",
        "II",
        "III",
        "IV-A",
        "IV-B",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",
        "X",
        "XI",
        "XII",
        "XIII",
        "ARMM",
        "BARMM",
        "NIR",
    }
)
ENCODINGS = frozenset({"cp1252", "utf-8"})
LAYOUT_SOURCE = "BIR RMC 160-2022 published Schedule 1 layout"
FIXTURE_SOURCE = "Supplied SRV/Maria DAT and matching validator log"
SOURCE_POLICY = "Source-preserving candidate policy; official validation pending"
NAME_POLICY = "Export name policy following supplied BIR surname rejections: Ñ to N; remove apostrophes; retain original names"
# Conservative candidate set, including punctuation present in the supplied names.
# This is not an exhaustive claim about every character the BIR module accepts.
NAME_CHARACTERS = frozenset(ascii_uppercase + " .-")
NAME_REPLACEMENTS = str.maketrans({"Ñ": "N", "ñ": "n", "'": "", "’": "", "‘": ""})
SORT_POLICY = "Export surname, given name, middle name, employee ID; ordinal comparison after name normalization"


def uppercase_name(value: str) -> str:
    """Uppercase without silently expanding characters such as ß to SS."""
    return "".join(c.upper() if len(c.upper()) == 1 else c for c in value)


def normalize_name(value: str) -> str:
    """Apply supported export substitutions, preserving other characters for validation."""
    return uppercase_name(normalize("NFC", value).translate(NAME_REPLACEMENTS)).strip(" ")


def sort_key(source: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_name(source["W"]),
        normalize_name(source["X"]),
        normalize_name(source["Y"]),
        source["A"].upper(),
    )
