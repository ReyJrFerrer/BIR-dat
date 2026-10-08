"""Landscape legal reports rendered directly from the shared snapshot."""

import io
from datetime import UTC, datetime
from decimal import Decimal
from html import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from .domain import ZERO, EmployeeAnnualRecord, Snapshot

# Three labeled lines keep every financial category readable at legal landscape size.
GROUPS = [
    (
        "Previous employer",
        [
            ("prior_gross", "Gross"),
            ("AJ", "Benefits"),
            ("AK", "De minimis"),
            ("AL", "Contributions"),
            ("AM", "Other non-tax"),
            ("prior_nontax", "Non-tax total"),
            ("AN", "Taxable basic"),
            ("AO", "Taxable benefits"),
            ("AP", "Taxable other"),
            ("prior_taxable", "Taxable total"),
        ],
    ),
    (
        "Present employer",
        [
            ("gross", "Gross"),
            ("E", "Benefits"),
            ("F", "De minimis"),
            ("G", "Contributions"),
            ("H", "Other non-tax"),
            ("I", "Non-tax total"),
            ("L", "Taxable basic"),
            ("M", "Taxable benefits"),
            ("N", "Taxable other"),
            ("O", "Taxable total"),
        ],
    ),
    (
        "Tax / withholding",
        [
            ("combined_taxable", "Combined taxable"),
            ("AR", "Annual tax"),
            ("AQ", "Prior withheld"),
            ("AS", "Jan–Nov withheld"),
            ("AT", "PERA"),
            ("additional", "December +"),
            ("refund", "Refund*"),
            ("adjusted", "Adjusted*"),
            ("P", "Present final"),
        ],
    ),
]
WIDTHS = [125] + [78] * 10
STYLE = ParagraphStyle("report", fontName="Helvetica", fontSize=8, leading=10)


def display(value: Decimal | None) -> str:
    return "Not supplied" if value is None else f"{value:,.2f}"


def paragraph(value: str, bold: bool = False) -> Paragraph:
    escaped = escape(value).replace("\n", "<br/>")
    return Paragraph(f"<b>{escaped}</b>" if bold else escaped, STYLE)


def report_table(
    record: EmployeeAnnualRecord | None, label: str, totals: dict[str, Decimal | None] | None = None
) -> Table:
    rows = []
    for title, columns in GROUPS:
        rows.append(
            [paragraph(title, True)]
            + [paragraph(name) for _, name in columns]
            + [""] * (10 - len(columns))
        )
        rows.append(
            [paragraph(label)]
            + [
                paragraph(display(record.amount(key) if record else (totals or {}).get(key)))
                for key, _ in columns
            ]
            + [""] * (10 - len(columns))
        )
    table = Table(rows, colWidths=WIDTHS, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#eeeeee"), colors.white]),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.black),
            ]
        )
    )
    return table


def render(snapshot: Snapshot, draft: bool = False) -> bytes:
    if not draft and not snapshot.valid:
        raise ValueError("Final PDF export is blocked by unresolved issues.")
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(1008, 612))
    pdf.setTitle("1604-C Schedule 1 alphalist" + (" — DRAFT" if draft else ""))
    keys = list(dict.fromkeys(key for _, columns in GROUPS for key, _ in columns))
    page_records: list[EmployeeAnnualRecord] = []
    page_number = 0
    y = 0.0

    def draw_paragraph(value: str, at: float, bold: bool = False) -> float:
        p = paragraph(value, bold)
        _, h = p.wrap(936, 500)
        p.drawOn(pdf, 36, at - h)
        return at - h

    def start_page() -> None:
        nonlocal page_number, y, page_records
        page_number += 1
        page_records = []
        y = draw_paragraph(
            "DRAFT — unresolved data"
            if draft
            else "ALPHALIST OF EMPLOYEES — SCHEDULE 1 — FOR BIR VALIDATION",
            584,
            True,
        )
        y = draw_paragraph(
            f"{snapshot.context.name or 'Employer not supplied'} | Year {snapshot.context.year or 'not supplied'} | "
            f"TIN {snapshot.context.tin or 'Not supplied'} / {snapshot.context.branch or 'Not supplied'}",
            y - 5,
        )
        y = draw_paragraph(
            "Form 1604-C annual compensation report • Converter-generated report • "
            + datetime.now(UTC).strftime("%Y-%m-%d")
            + f" • Page {page_number}",
            y - 4,
        )
        if draft:
            y = draw_paragraph(
                "Source/proposed amounts only. *Refund and adjusted amounts are not proof of payment. "
                "See validation summary for unresolved classifications and mappings.",
                y - 4,
            )
        else:
            y = draw_paragraph(
                "Source-preserving candidate. Review notes accompany the JSON report. "
                "*Computed refund/adjusted withholding is not proof of payment or official BIR approval.",
                y - 4,
            )
        y -= 12

    def totals_for(records: list[EmployeeAnnualRecord]) -> dict[str, Decimal | None]:
        result = {}
        for key in keys:
            amounts = [r.amount(key) for r in records]
            result[key] = (
                None
                if any(v is None for v in amounts)
                else sum((v for v in amounts if v is not None), ZERO)
            )
        return result

    def draw_table(table: Table) -> None:
        nonlocal y
        _, height = table.wrap(936, 500)
        table.drawOn(pdf, 36, y - height)
        y -= height + 8

    def close_page(last: bool) -> None:
        nonlocal y
        draw_table(report_table(None, "Page subtotal", totals_for(page_records)))
        if last:
            draw_table(report_table(None, "Grand total", totals_for(list(snapshot.records))))
            y = draw_paragraph("END OF REPORT", y, True)
        pdf.setFont("Helvetica", 7)
        pdf.drawString(36, 16, f"Source SHA-256: {snapshot.source_hash} | {snapshot.profile}")
        pdf.showPage()

    start_page()
    # Reserve complete page and grand totals on every page. This avoids orphan totals.
    total_height = report_table(None, "Grand total", {k: ZERO for k in keys}).wrap(936, 500)[1] + 8
    reserve = total_height * 2 + 35
    for sequence, record in enumerate(snapshot.records, 1):
        source = dict(record.source)
        heading = (
            f"{sequence}. {record.name} | ID {record.employee_id} | TIN {record.tin or 'Not supplied'} | "
            f"Employment {source['C'] or 'Not supplied'} to {source['D'] or 'Not supplied'} | "
            f"Substituted filing: {source['AD'] or 'Not supplied'}"
        )
        p = paragraph(heading, True)
        heading_height = p.wrap(936, 500)[1]
        table = report_table(record, "Compensation / PHP")
        height = table.wrap(936, 500)[1] + heading_height + 15
        if y - height < reserve and page_records:
            close_page(False)
            start_page()
        if y - height < reserve:
            raise ValueError(
                "Employee row is too tall for the report layout; review unusually long fields."
            )
        y = draw_paragraph(heading, y, True) - 5
        draw_table(table)
        page_records.append(record)
    close_page(True)
    pdf.save()
    return stream.getvalue()
