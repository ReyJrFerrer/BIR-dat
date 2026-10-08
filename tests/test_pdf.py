"""Rendered geometry and financial reconciliation of the BIR print layout."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from alphalist.conversion import build_snapshot
from alphalist.pdf import render
from alphalist.review import load_reference

REFERENCE = Path(__file__).resolve().parents[1] / "res/Test-1.pdf"


def workbook_snapshot():
    return build_snapshot(load_reference("workbook"))


def spans(page):
    return [
        span
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for span in line["spans"]
    ]


def band_amounts(page, y):
    return [
        Decimal(span["text"].strip().replace(",", ""))
        for span in spans(page)
        if abs(span["origin"][1] - y) < 1 and span["bbox"][0] >= 309 and "." in span["text"]
    ]


def test_reference_headings_font_sizes_positions_and_rules():
    doc = pymupdf.open(stream=render(workbook_snapshot(), draft=True))
    reference = pymupdf.open(REFERENCE)
    page = doc[0]
    assert page.rect == reference[0].rect
    output = spans(page)
    for span in spans(reference[0]):
        if span["origin"][1] >= 253 or span["text"] in {
            "PAGE    1",
            "684-785-510-000",
            ",",
            " 2025",
        }:
            continue
        actual = min(
            (item for item in output if item["text"] == span["text"]),
            key=lambda item: sum(
                abs(a - b) for a, b in zip(item["origin"], span["origin"], strict=True)
            ),
        )
        assert actual["origin"] == pytest.approx(span["origin"], abs=0.01)
        assert actual["size"] == pytest.approx(span["size"], abs=0.001)
        assert actual["font"] == (
            "CourierNewPS-BoldMT" if span["font"] == "CIDFont+F1" else "CourierNewPSMT"
        )
    actual_rules = page.get_drawings()
    expected_rules = reference[0].get_drawings()
    assert len(actual_rules) == len(expected_rules)
    for actual, expected in zip(actual_rules, expected_rules, strict=True):
        assert tuple(actual["rect"]) == pytest.approx(tuple(expected["rect"]), abs=0.01)
        assert actual["width"] == pytest.approx(expected["width"], abs=0.001)
    assert "Helvetica" not in {span["font"] for span in spans(page)}


def test_printed_columns_include_basic_pay_and_all_nontaxable_components():
    snapshot = workbook_snapshot()
    carlo = next(record for record in snapshot.records if record.employee_id == "EMP-0015")
    pdf = pymupdf.open(stream=render(replace(snapshot, records=(carlo,)), draft=True))
    top = [
        Decimal(value)
        for value in (
            "25000",
            "6000",
            "12000",
            "0",
            "257000",
            "257000",
            "27500",
            "6000",
            "13200",
            "0",
        )
    ]
    bottom = [
        Decimal(value)
        for value in (
            "316800",
            "573800",
            "57260",
            "1050",
            "45000",
            "0",
            "11210",
            "0",
            "57260",
        )
    ]
    assert band_amounts(pdf[0], 261.24) == top
    assert band_amounts(pdf[0], 272.40) == bottom
    assert band_amounts(pdf[0], 585.24) == top
    assert band_amounts(pdf[0], 598.68) == bottom
    assert band_amounts(pdf[1], 11.52) == top
    assert band_amounts(pdf[1], 25.68) == bottom


def test_pagination_repeats_headings_keeps_every_row_and_reconciles_totals():
    snapshot = workbook_snapshot()
    snapshot = replace(snapshot, records=snapshot.records * 3)
    doc = pymupdf.open(stream=render(snapshot, draft=True))
    assert len(doc) == 4
    sequences = []
    page_totals = []
    for index, page in enumerate(doc):
        assert "DRAFT" in page.get_text()
        # All visible text, including the bottom total rule, stays on paper.
        for span in spans(page):
            assert page.rect.contains(pymupdf.Rect(span["bbox"]))
        if index == len(doc) - 1:
            break
        assert f"PAGE    {index + 1}" in page.get_text()
        assert "PAGE TOTAL:" in page.get_text()
        sequences.extend(
            int(span["text"])
            for span in spans(page)
            if span["bbox"][0] < 100 and 250 < span["origin"][1] < 560
        )
        page_totals.append(band_amounts(page, 598.68))
    assert sequences == list(range(1, 34))
    grand_totals = band_amounts(doc[-1], 25.68)
    assert grand_totals == [sum(column) for column in zip(*page_totals, strict=True)]
    assert grand_totals[1] == snapshot.total("combined_taxable")
    assert grand_totals[2] == snapshot.total("AR")
    assert "END OF REPORT" in doc[-1].get_text()
    assert "ALPHALIST OF EMPLOYEES" not in doc[-1].get_text()


def test_long_names_wrap_without_overlapping_amounts_and_remain_in_notes():
    snapshot = workbook_snapshot()
    record = snapshot.records[0]
    source = dict(record.source) | {"W": "A" * 50, "X": "B" * 50, "Y": "C" * 50}
    record = replace(record, source=tuple(source.items()))
    doc = pymupdf.open(stream=render(replace(snapshot, records=(record,) * 12), draft=True))
    assert len(doc) > 2
    for page in list(doc)[:-1]:
        name_spans = [
            span
            for span in spans(page)
            if abs(span["origin"][0] - 180.72) < 0.01 and span["origin"][1] > 250
        ]
        assert name_spans
        assert all(span["bbox"][2] < 309 for span in name_spans)
        assert all(span["bbox"][3] < 560 for span in name_spans)
        assert "".join(span["text"].replace(" ", "") for span in name_spans).count(
            record.export_name.replace(" ", "")
        ) == len(list(page.annots()))


def test_unknown_amounts_remain_unknown_in_rows_and_totals():
    snapshot = workbook_snapshot()
    record = snapshot.records[0]
    amounts = dict(record.amounts) | {"F": None}
    record = replace(record, amounts=tuple(amounts.items()))
    doc = pymupdf.open(stream=render(replace(snapshot, records=(record,)), draft=True))
    for page, ys in ((doc[0], (261.24, 585.24)), (doc[1], (11.52,))):
        for y in ys:
            matching = [
                span
                for span in spans(page)
                if abs(span["origin"][1] - y) < 1 and span["text"] == "NOT SUPPLIED"
            ]
            assert len(matching) == 1
            assert 780 < matching[0]["bbox"][0] < 843


def test_font_subset_falls_back_for_characters_missing_from_reference():
    snapshot = workbook_snapshot()
    context = replace(snapshot.context, name="QUICK 'Z' & JAZZ 4789", year="2049")
    doc = pymupdf.open(stream=render(replace(snapshot, context=context), draft=True))
    text = doc[0].get_text()
    assert "QUICK 'Z' & JAZZ 4789" in text
    assert "2049" in text
