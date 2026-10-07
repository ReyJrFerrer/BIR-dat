"""Prioritized tasks for people, retaining the full validation result for exports."""

from collections import defaultdict
from dataclasses import dataclass

from .conversion import DECLARATIONS
from .domain import Snapshot, ValidationIssue

QUESTION_HELP = {
    "schedule": (
        "Employee classification",
        "Are these employees confirmed as non-minimum-wage earners? Income alone cannot answer this.",
    ),
    "prior": (
        "Empty previous-employer sections",
        "Do the empty sections mean no previous employer? Employees with populated sections retain their previous-employer data.",
    ),
    "withholding": (
        "Final annual amounts",
        "Are annual tax and present withholding finalized, including any processed adjustments?",
    ),
    "tax_treatment": (
        "Tax treatment",
        "Does the ordinary graduated annual tax treatment apply? Record exceptions on the employee record.",
    ),
    "benefits": (
        "Non-taxable compensation",
        "Have the benefit categories and combined annual exclusion been reviewed?",
    ),
    "substituted": (
        "Substituted filing",
        "Has eligibility for the Yes / No answers in the workbook been reviewed?",
    ),
}
ANSWER_LABELS = {
    "unknown": "Not known — leave unresolved",
    "confirmed": "Confirmed by supporting information",
    "non_mwe": "Confirmed: not minimum wage earners",
    "mwe": "Minimum wage earners — Schedule 2 needed",
    "none": "Confirmed: no previous employer for empty sections",
    "present": "Previous employer information is needed",
    "inherit": "Use the shared answer",
}
PROFILE_LABELS = {
    "YEAR_PROFILE": "Reporting year support",
    "NAME_ENCODING": "Names with special characters",
    "NAME_WIDTH": "Long employee names",
    "REFUND_PROFILE": "Refund handling",
    "PRIOR_PROFILE": "Previous-employer mapping",
    "CODE_PROFILE": "Additional employee codes and tax treatments",
    "PERA_PROFILE": "PERA tax credits",
    "BENEFIT_PROFILE": "Benefit classification",
    "LOW_INCOME_PROFILE": "Low-income employee mapping",
    "ORDERING_PROFILE": "Multi-employee output ordering",
}
FIELD_GROUPS = [
    ("Identity and employment", "A B V W X Y Z C D AA AB AC AD".split()),
    ("Present compensation", "E F G H I J K L M N O".split()),
    ("Tax and withholding", "P AR AS AT".split()),
    ("Previous employer", "AE AF AG AH AI AJ AK AL AM AN AO AP AQ".split()),
    ("Source estimates and diagnostics", "Q R S T U".split()),
]


@dataclass(frozen=True)
class IssueGroup:
    key: str
    label: str
    issues: tuple[ValidationIssue, ...]


def data_tasks(snapshot: Snapshot, row_key: str | None = None) -> tuple[IssueGroup, ...]:
    groups: dict[tuple[str, str], list[ValidationIssue]] = defaultdict(list)
    for issue in snapshot.issues:
        if issue.severity == "error" and issue.category == "data":
            if row_key is None or issue.row_key == row_key:
                groups[(issue.row_key, issue.field)].append(issue)
    return tuple(
        IssueGroup(f"{row}:{field}", items[0].message, tuple(items))
        for (row, field), items in groups.items()
    )


def grouped_issues(snapshot: Snapshot, category: str) -> tuple[IssueGroup, ...]:
    groups: dict[str, list[ValidationIssue]] = defaultdict(list)
    for issue in snapshot.issues:
        if issue.severity == "error" and issue.category == category:
            groups[issue.field if category == "review" else issue.code].append(issue)
    return tuple(
        IssueGroup(
            key,
            QUESTION_HELP[key][0] if key in QUESTION_HELP else PROFILE_LABELS.get(key, key),
            tuple(items),
        )
        for key, items in groups.items()
    )


def question_options() -> dict[str, tuple[str, list[str]]]:
    return {key: (QUESTION_HELP[key][0], definition[1]) for key, definition in DECLARATIONS.items()}
