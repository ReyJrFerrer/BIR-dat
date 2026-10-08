"""Value objects shared by ingestion, validation, and presentation."""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .profiles import normalize_name, uppercase_name

FIXTURES = Path(__file__).with_name("fixtures")
PROFILE = "1604C-2025-schedule1-candidate-v3"
REFERENCE_HASH = "59892d6a782fb46aa44060ec9ca74db5ae3a3862eb247513908b8bb6a519c788"
LOG_HASH = "acc3b57944f1232a456d77ac8417ae12829636a7b93ad9278b495240818f9505"
WORKBOOK = FIXTURES / "Kalamansi Trading 1604CF Annualization 2025.xlsx"
REFERENCE = FIXTURES / "6847855100000123120251604C.DAT"
REFERENCE_LOG = REFERENCE.with_suffix(".TXT")
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class FilingContext:
    name: str = ""
    tin: str = ""
    branch: str = ""
    year: str = "2025"
    encoding: str = "cp1252"


@dataclass
class SourceRow:
    key: str
    values: dict[str, str]
    cells: dict[str, str]


@dataclass
class SourceWorkbook:
    filename: str
    sha256: str
    sheet: str
    rows: list[SourceRow]
    context: FilingContext
    totals: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    code: str
    employee: str
    row_key: str
    cell: str
    field: str
    observed: str
    message: str
    remedy: str
    category: str = "data"


@dataclass(frozen=True)
class EmployeeAnnualRecord:
    key: str
    employee_id: str
    name: str
    tin: str
    source: tuple[tuple[str, str], ...]
    amounts: tuple[tuple[str, Decimal | None], ...]
    detail: tuple[str, ...] | None

    @property
    def export_name(self) -> str:
        source = dict(self.source)
        surname, given, middle = (normalize_name(source[field]) for field in ("W", "X", "Y"))
        return f"{surname}, {given} {middle}".strip()

    @property
    def name_adjusted(self) -> bool:
        source = dict(self.source)
        return any(
            normalize_name(source[field]) != uppercase_name(source[field])
            for field in ("W", "X", "Y")
        )

    def amount(self, key: str) -> Decimal | None:
        return dict(self.amounts).get(key)


@dataclass(frozen=True)
class AutomaticMapping:
    code: str
    employee: str
    row_key: str
    field: str
    cell: str
    before: str
    after: str
    reason: str
    basis: str


@dataclass(frozen=True)
class Snapshot:
    context: FilingContext
    records: tuple[EmployeeAnnualRecord, ...]
    issues: tuple[ValidationIssue, ...]
    source_hash: str
    profile: str = PROFILE
    mappings: tuple[AutomaticMapping, ...] = ()

    @property
    def valid(self) -> bool:
        """Complete enough to export for validation; not official BIR approval."""
        return bool(self.records) and not any(i.severity == "error" for i in self.issues)

    def total(self, field: str) -> Decimal | None:
        values = [r.amount(field) for r in self.records]
        if any(v is None for v in values):
            return None
        return sum((v for v in values if v is not None), ZERO)


@dataclass
class Correction:
    scope: str
    field: str
    before: str
    after: str
    reason: str
    timestamp: str


@dataclass
class Evidence:
    dat_hash: str
    log_hash: str
    version: str
    text: str
    origin: str


@dataclass
class Review:
    source: SourceWorkbook
    overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    context_overrides: dict[str, str] = field(default_factory=dict)
    declarations: dict[str, dict[str, str]] = field(default_factory=dict)
    filing_declarations: dict[str, str] = field(default_factory=dict)
    history: list[Correction] = field(default_factory=list)
    evidence: Evidence | None = None
    revision: int = 0
