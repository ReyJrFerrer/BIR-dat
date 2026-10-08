"""BIR-style two-line alphalist, using the shared financial snapshot.

Coordinates are points measured from the top of res/Test-1.pdf. Static headings
and embedded font subsets live in pdf_assets; no employee data is templated.
"""

import io
import json
from collections.abc import Sequence
from decimal import Decimal
from functools import lru_cache
from itertools import groupby
from pathlib import Path
from textwrap import wrap

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .domain import ZERO, EmployeeAnnualRecord, Snapshot

ASSETS = Path(__file__).with_name("pdf_assets")
PAGE_SIZE = (1008, 612)
BODY_SIZE = 6.9552
TITLE_SIZE = 9.9534
FIRST_ROW = 261.24
ROW_STEP = 25.44
ROW_LIMIT = 559.0
# The older printed form groups basic salaries and de minimis with other pay.
# Every compensation component is included exactly once in its printed group.
TOP_FIELDS = (
    ("AJ",),
    ("AK", "AM"),
    ("AL",),
    ("AO",),
    ("AN", "AP"),
    ("prior_taxable",),
    ("E",),
    ("F", "H"),
    ("G",),
    ("M",),
)
BOTTOM_FIELDS = (
    ("L", "N"),
    ("combined_taxable",),
    ("AR",),
    ("AQ",),
    ("AS",),
    ("AT",),
    ("additional",),
    ("refund",),
    ("adjusted",),
)
AMOUNT_RIGHTS = (362.70, 434.97, 500.70, 562.98, 629.70, 694.38, 775.98, 837.54, 898.98, 961.26)


def display(value: Decimal | None) -> str:
    """Shared web display (the printed form uppercases unknown values)."""
    return "Not supplied" if value is None else f"{value:,.2f}"


@lru_cache(maxsize=2)
def report_font(bold: bool = False) -> TTFont:
    name = "BIR-CourierNew" + ("-Bold" if bold else "")
    filename = "CourierNew-Bold.ttf" if bold else "CourierNew.ttf"
    font = TTFont(name, str(ASSETS / filename))
    pdfmetrics.registerFont(font)
    return font


@lru_cache(maxsize=1)
def header_layout() -> dict:
    return json.loads((ASSETS / "header.json").read_text())


def printed_amount(record: EmployeeAnnualRecord, fields: tuple[str, ...]) -> Decimal | None:
    values = [record.amount(field) for field in fields]
    return (
        None
        if any(value is None for value in values)
        else sum((value for value in values if value is not None), ZERO)
    )


def total_amount(
    records: Sequence[EmployeeAnnualRecord], fields: tuple[str, ...]
) -> Decimal | None:
    values = [printed_amount(record, fields) for record in records]
    return (
        None
        if any(value is None for value in values)
        else sum((value for value in values if value is not None), ZERO)
    )


def format_tin(tin: str, branch: str = "") -> str:
    digits = tin.replace("-", "").replace(" ", "")
    if len(digits) == 13 and digits.isascii() and digits.isdigit():
        digits, branch = digits[:9], digits[9:]
    if len(digits) == 9 and digits.isascii() and digits.isdigit():
        # The reference uses three branch digits in the employer heading, four
        # in employee rows. Keep nonzero four-digit branches intact.
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" + (f"-{branch}" if branch else "")
    return tin or "NOT SUPPLIED"


class Report:
    def __init__(self, pdf: canvas.Canvas, snapshot: Snapshot, draft: bool) -> None:
        self.pdf = pdf
        self.snapshot = snapshot
        self.draft = draft

    def text(
        self,
        value: str,
        x: float,
        y: float,
        *,
        size: float = BODY_SIZE,
        bold: bool = False,
        right: bool = False,
        width: float | None = None,
        measured_width: float | None = None,
    ) -> None:
        font = report_font(bold)
        # Reference fonts are subsets. Render absent glyphs with standard
        # Courier instead of emitting blank glyphs for draft/source text.
        runs = [
            (
                font.fontName if supported else ("Courier-Bold" if bold else "Courier"),
                "".join(chars),
            )
            for supported, chars in groupby(value, lambda char: ord(char) in font.face.charToGlyph)
        ]
        natural_width = sum(pdfmetrics.stringWidth(text, name, size) for name, text in runs)
        scale = min(1.0, width / natural_width) if width and natural_width else 1.0
        if right:
            x -= natural_width * scale
        text = self.pdf.beginText(x, PAGE_SIZE[1] - y)
        text.setHorizScale(scale * 100)
        text.setCharSpace(0)
        if measured_width is not None and len(value) > 1:
            text.setCharSpace((measured_width - natural_width) / (len(value) - 1))
        for name, content in runs:
            text.setFont(name, size)
            text.textOut(content)
        self.pdf.drawText(text)

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.pdf.line(x1, PAGE_SIZE[1] - y1, x2, PAGE_SIZE[1] - y2)

    def header(self, page_number: int) -> None:
        for item in header_layout()["text"]:
            self.text(
                item["text"],
                item["x"],
                item["y"],
                size=item["size"],
                bold=item["bold"],
                measured_width=item["width"],
            )
        self.pdf.setLineWidth(0.72)
        self.pdf.setLineCap(1)
        for line in header_layout()["lines"]:
            self.line(*line)
        context = self.snapshot.context
        self.text(f" {context.year or 'NOT SUPPLIED'}", 563.16, 61.20, size=TITLE_SIZE, bold=True)
        self.text(f"PAGE    {page_number}", 891, 25.80, size=TITLE_SIZE)
        self.text(context.name.upper() or "NOT SUPPLIED", 267, 87.96, size=TITLE_SIZE, width=242)
        branch = context.branch
        if len(branch) == 4 and branch.startswith("0"):
            branch = branch[1:]
        employer_tin = format_tin(context.tin, branch)
        if not context.branch and context.tin:
            employer_tin += " / NOT SUPPLIED"
        self.text(employer_tin, 639, 88.80, size=TITLE_SIZE, width=180)
        self.draft_mark()

    def draft_mark(self, y: float = 25.80) -> None:
        if self.draft:
            self.text("DRAFT - UNRESOLVED DATA", 79.44, y, bold=True)

    def amounts(
        self,
        values: Sequence[Decimal | None],
        y: float = 0,
        *,
        positions: Sequence[Sequence[float]] | None = None,
    ) -> None:
        positions = (
            positions if positions is not None else [(x, y) for x in AMOUNT_RIGHTS[: len(values)]]
        )
        for index, (value, (x, baseline)) in enumerate(zip(values, positions, strict=True)):
            left = positions[index - 1][0] + 6 if index else 309
            self.text(display(value).upper(), x, baseline, right=True, width=x - left)

    def employee(self, record: EmployeeAnnualRecord, sequence: int, y: float) -> float:
        name_lines = wrap(record.export_name, width=30) or ["NOT SUPPLIED"]
        height = max(ROW_STEP, len(name_lines) * 9 + 7.44)
        self.text(str(sequence), 97.42, y + 1.44, right=True, width=24)
        self.text(format_tin(record.tin), 106.44, y + 1.44, width=67.13)
        for index, name in enumerate(name_lines):
            self.text(name, 180.72, y + 1.44 + index * 9)
        self.amounts([printed_amount(record, fields) for fields in TOP_FIELDS], y)
        self.amounts([printed_amount(record, fields) for fields in BOTTOM_FIELDS], y + 11.16)
        source = dict(record.source)
        substituted = {"yes": "Y", "no": "N"}.get(source.get("AD", "").lower(), "?")
        self.text(substituted, 953.16, y + 10.44)
        # Keep audit context available as a PDF note without adding columns or
        # extra printed lines to the BIR layout.
        note = f"Employee ID: {record.employee_id}"
        if record.name_adjusted:
            note += f"\nOriginal: {record.name}"
        self.pdf.textAnnotation(
            note,
            Rect=(180.72, PAGE_SIZE[1] - y - height + 7, 306, PAGE_SIZE[1] - y + 7),
            relative=0,
            Name="Comment",
            F=2,
        )
        return height

    def totals(self, records: Sequence[EmployeeAnnualRecord], *, grand: bool = False) -> None:
        layout = header_layout()["grand_total" if grand else "page_total"]
        for item in layout["text"]:
            self.text(item["text"], item["x"], item["y"])
        for fields, positions in zip((TOP_FIELDS, BOTTOM_FIELDS), layout["amounts"], strict=True):
            self.amounts([total_amount(records, group) for group in fields], positions=positions)


def render(snapshot: Snapshot, draft: bool = False) -> bytes:
    if not draft and not snapshot.valid:
        raise ValueError("Final PDF export is blocked by unresolved issues.")
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=PAGE_SIZE)
    pdf.setTitle("1604-C Schedule 1 alphalist" + (" - DRAFT" if draft else ""))
    pdf.setSubject(
        "Candidate for BIR validation. Computed refund/adjusted withholding is not proof of payment "
        "or official BIR approval. Review notes accompany the JSON report. "
        f"Source SHA-256: {snapshot.source_hash} | {snapshot.profile}"
    )
    report = Report(pdf, snapshot, draft)
    page_number = 1
    report.header(page_number)
    y = FIRST_ROW
    page_records: list[EmployeeAnnualRecord] = []
    for sequence, record in enumerate(snapshot.records, 1):
        height = max(ROW_STEP, len(wrap(record.export_name, width=30)) * 9 + 7.44)
        if y + height > ROW_LIMIT and page_records:
            report.totals(page_records)
            pdf.showPage()
            page_number += 1
            report.header(page_number)
            page_records = []
            y = FIRST_ROW
        if y + height > ROW_LIMIT:
            raise ValueError(
                "Employee row is too tall for the report layout; review unusually long fields."
            )
        y += report.employee(record, sequence, y)
        page_records.append(record)
    report.totals(page_records)
    pdf.showPage()
    # Test-1's grand-total band continues on a separate sheet without headers.
    report.draft_mark(79.80)
    report.totals(snapshot.records, grand=True)
    pdf.showPage()
    pdf.save()
    return stream.getvalue()
