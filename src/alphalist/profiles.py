"""Documented and provisional rules for a source-preserving validation candidate.

See docs/mapping-policy.md for evidence and the limits of this profile.
"""

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
ENCODING_POLICY = "Lossless encoding policy; target validator character acceptance pending"
SORT_POLICY = "Surname, given name, middle name, employee ID; ordinal comparison after uppercasing"


def sort_key(source: dict[str, str]) -> tuple[str, str, str, str]:
    return (source["W"].upper(), source["X"].upper(), source["Y"].upper(), source["A"].upper())
