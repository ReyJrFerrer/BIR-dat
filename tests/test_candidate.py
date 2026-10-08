"""Candidate regressions use only existing identifiers from supplied artifacts.

Selected rows are explicit in-memory unit inputs, never a partial export of the
Kalamansi filing. No corrected demo workbook or substitute TIN is created.
"""

import copy
import csv
import io
from dataclasses import replace
from decimal import Decimal

import pytest
from pypdf import PdfReader

from alphalist.conversion import build_snapshot
from alphalist.dat import CONTROL_INDICES, digest, serialize, verify
from alphalist.pdf import render
from alphalist.review import audit, correct, load_reference, status


def supplied_rows(*employee_ids):
    review = load_reference("workbook")
    reference = load_reference("validated")
    review.source = replace(
        review.source,
        filename="Explicit supplied rows for mapping regression",
        context=reference.source.context,
        totals={},
        rows=[r for r in review.source.rows if r.values["A"] in employee_ids],
    )
    assert len(review.source.rows) == len(employee_ids)
    return review


def decoded_rows(snapshot):
    return list(csv.reader(serialize(snapshot).decode(snapshot.context.encoding).splitlines()))


def test_multi_employee_candidate_exports_all_supplied_unit_rows():
    review = supplied_rows("EMP-0007", "EMP-0011", "EMP-0004", "EMP-0015", "EMP-0012", "EMP-0014")
    original = copy.deepcopy(review.source)
    snapshot = build_snapshot(review)
    assert snapshot.valid
    assert status(review) == "Ready for BIR validation"
    assert review.source == original
    rows = decoded_rows(snapshot)
    assert len(rows) == 8
    assert [row[5] for row in rows[1:-1]] == ["1", "2", "3", "4", "5", "6"]
    for i, value in zip(CONTROL_INDICES, rows[-1][5:], strict=True):
        assert sum(Decimal(row[i]) for row in rows[1:-1]) == Decimal(value)
    assert audit(review)["output_hash"] == digest(serialize(snapshot))
    assert len(audit(review)["automatic_mappings"]) > 0
    assert not audit(review)["evidence_matches_current_output"]
    review.source.rows.reverse()
    assert serialize(build_snapshot(review)) == serialize(snapshot)


def test_previous_employer_and_refund_fields_match_shared_snapshot():
    snapshot = build_snapshot(supplied_rows("EMP-0011", "EMP-0015"))
    details = {r[8]: r for r in decoded_rows(snapshot)[1:-1]}
    carlo = details["VILLANUEVA"]
    assert [carlo[i - 1] for i in [23, 36, 37, 38, 39, 40, 41, 42, 43, 44]] == [
        "257000.00",
        "316800.00",
        "573800.00",
        "573800.00",
        "57260.00",
        "1050.00",
        "45000.00",
        "11210.00",
        "0.00",
        "57260.00",
    ]
    pedro = details["SANTOS JR"]
    assert [pedro[i - 1] for i in [42, 43, 44]] == ["0.00", "3825.00", "196175.00"]
    pdf = PdfReader(io.BytesIO(render(snapshot)))
    text = "\n".join(p.extract_text() for p in pdf.pages)
    assert "3,825.00" in text and "573,800.00" in text
    assert "REPORTED UNDER FORM 2316" in text
    assert "proof of payment" in pdf.metadata.subject


def test_rejected_surnames_are_normalized_without_changing_source_or_financials():
    review = supplied_rows("EMP-0004", "EMP-0012", "EMP-0007", "EMP-0014")
    original = copy.deepcopy(review.source)
    snapshot = build_snapshot(review)
    output = serialize(snapshot)
    rows = decoded_rows(snapshot)
    assert [row[8] for row in rows[1:-1]] == ["LOPEZ", "NUNEZ", "OBRIEN-SANTOS", "REYES"]
    assert [row[5] for row in rows[1:-1]] == ["1", "2", "3", "4"]
    assert b"\xd1" not in output and b"'" not in output
    assert all(len(row) == 49 for row in rows[1:-1])
    assert review.source == original
    assert not review.history and not review.overrides
    for record in snapshot.records:
        source = dict(record.source)
        for field in ("I", "O", "P", "AQ", "AR", "AS"):
            # These supplied rows have empty previous-employer blocks: AQ stays zero.
            assert record.amount(field) == Decimal(source[field] or "0")
    for index, control in zip(CONTROL_INDICES, rows[-1][5:], strict=True):
        assert sum(Decimal(row[index]) for row in rows[1:-1]) == Decimal(control)
    mappings = [
        m for m in audit(review)["automatic_mappings"] if m["code"] == "NAME_NORMALIZATION"
    ]
    assert {(m["cell"], m["before"], m["after"]) for m in mappings} == {
        ("W9", "Ñunez", "NUNEZ"),
        ("W13", "O'Brien-Santos", "OBRIEN-SANTOS"),
    }
    assert {r.employee_id: r.name for r in snapshot.records}["EMP-0004"] == "Ñunez, Ana Liza Cruz"
    assert not any(i.code in ("CHARACTER_ACCEPTANCE", "NAME_ESCAPING") for i in snapshot.issues)
    correct(review, "context", {"encoding": "utf-8"}, "Test explicit lossless encoding selection")
    utf_snapshot = build_snapshot(review)
    assert serialize(utf_snapshot) == output
    verify(serialize(utf_snapshot), encoding="utf-8")


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("W", "ñu'nez", "NUNEZ"),
        ("X", "Ñu’nez", "NUNEZ"),
        ("Y", "N\u0303u‘nez", "NUNEZ"),
    ],
)
def test_normalization_applies_to_all_name_fields_and_both_encodings(field, value, expected, encoding):
    review = load_reference("validated")
    correct(review, "context", {"encoding": encoding})
    correct(review, "6", {field: value})
    snapshot = build_snapshot(review)
    assert snapshot.valid
    fields = decoded_rows(snapshot)[1]
    assert len(fields) == 49
    assert fields[{"W": 8, "X": 9, "Y": 10}[field]] == expected
    assert dict(snapshot.records[0].source)[field] == value
    assert any(m.field == field and m.before == value and m.after == expected for m in snapshot.mappings)


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("W", 'Reyes, "Maria"'),
        ("X", "Maria &"),
        ("Y", "Santos?"),
        ("W", "Reyes 漢"),
        ("X", "María"),
        ("Y", "Santos\u200b"),
        ("W", "Reyeß"),
        ("X", "Maria1"),
    ],
)
def test_unsupported_name_characters_block_downloads_under_either_encoding(field, value, encoding):
    review = load_reference("validated")
    correct(review, "context", {"encoding": encoding})
    correct(review, "6", {field: value})
    snapshot = build_snapshot(review)
    assert any(i.field == field and i.code == "NAME_CHARACTERS" and i.severity == "error" for i in snapshot.issues)
    assert dict(snapshot.records[0].source)[field] == value
    assert not snapshot.valid
    with pytest.raises(ValueError, match="blocked"):
        serialize(snapshot)
    with pytest.raises(ValueError, match="blocked"):
        render(snapshot)


@pytest.mark.parametrize("field", ["W", "X"])
def test_required_names_cannot_become_empty_after_normalization(field):
    review = load_reference("validated")
    correct(review, "6", {field: "'‘’"})
    snapshot = build_snapshot(review)
    assert any(i.code == "NAME_REQUIRED" and i.field == field for i in snapshot.issues)
    with pytest.raises(ValueError, match="blocked"):
        serialize(snapshot)


def test_blank_middle_name_and_supported_punctuation_remain_valid():
    review = supplied_rows("EMP-0014", "EMP-0012")
    correct(review, "13", {"Y": ""})
    snapshot = build_snapshot(review)
    assert snapshot.valid
    rows = decoded_rows(snapshot)
    assert rows[1][9] == "MA. CRISTINA"
    assert rows[2][8] == "OBRIEN-SANTOS"
    assert rows[2][10] == ""


@pytest.mark.parametrize("surname", ["O'BRIEN", "ÑUNEZ", "REYES?", "", "A" * 51])
def test_serialized_verification_rejects_unresolved_name_content(surname):
    data = serialize(build_snapshot(load_reference("validated")))
    changed = data.replace(b'"REYES"', f'"{surname}"'.encode("cp1252"))
    with pytest.raises(ValueError, match="export name"):
        verify(changed)


def test_pdf_uses_dat_name_order_and_retains_original_spellings():
    review = supplied_rows("EMP-0004", "EMP-0012")
    snapshot = build_snapshot(review)
    names = [row[8] for row in decoded_rows(snapshot)[1:-1]]
    assert names == ["NUNEZ", "OBRIEN-SANTOS"]
    pdf = PdfReader(io.BytesIO(render(snapshot)))
    text = " ".join(" ".join(p.extract_text() for p in pdf.pages).split())
    assert text.index("NUNEZ, ANA LIZA CRUZ") < text.index("OBRIEN-SANTOS, MARK ANTHONY VILLAR")
    notes = "\n".join(
        str(annotation.get_object().get("/Contents", ""))
        for page in pdf.pages
        for annotation in page.get("/Annots", [])
    )
    assert "Original: Ñunez, Ana Liza Cruz" in notes
    assert "Original: O'Brien-Santos, Mark Anthony Villar" in notes
    assert "GRAND TOTAL:" in text


@pytest.mark.parametrize(
    "employee_id", ["EMP-0002", "EMP-0004", "EMP-0003", "EMP-0005", "EMP-0016"]
)
def test_low_income_is_not_automatically_reclassified(employee_id):
    review = supplied_rows(employee_id)
    snapshot = build_snapshot(review)
    record = snapshot.records[0]
    source = dict(record.source)
    assert record.detail[32] == f"{Decimal(source['L']):.2f}"
    assert record.detail[35] == f"{Decimal(source['O']):.2f}"
    assert record.detail[38] == f"{Decimal(source['AR']):.2f}"
    assert record.detail[26] == "0.00"
    assert any(
        i.code == "LOW_INCOME_VALIDATION" and i.severity == "warning" for i in snapshot.issues
    )
    assert not review.declarations
    if employee_id == "EMP-0003":
        assert not snapshot.valid  # Liza's missing identifier is never synthesized.
    else:
        assert snapshot.valid


def test_declared_mwe_and_nonzero_pera_remain_blocking():
    review = load_reference("validated")
    correct(review, "6", {"schedule": "mwe"}, "Test unsupported schedule")
    assert not build_snapshot(review).valid
    assert any(
        i.code == "UNSUPPORTED_MWE" and i.severity == "error" for i in build_snapshot(review).issues
    )
    review = load_reference("validated")
    correct(review, "6", {"AT": "1.00"}, "Test unsupported PERA credit")
    assert not build_snapshot(review).valid
    with pytest.raises(ValueError, match="blocked"):
        serialize(build_snapshot(review))


def test_foreign_nationality_and_benefit_categories_stay_source_driven():
    review = supplied_rows("EMP-0012", "EMP-0014")
    snapshot = build_snapshot(review)
    assert snapshot.valid
    records = {r.employee_id: r for r in snapshot.records}
    assert records["EMP-0012"].detail[44] == "AMERICAN"
    assert records["EMP-0012"].detail[45] == "CP"
    assert records["EMP-0012"].amount("AR") == Decimal("117500.00")
    assert records["EMP-0014"].amount("H") == Decimal("8000.00")
    assert any(i.code == "FOREIGN_TAX_TREATMENT" for i in snapshot.issues)
    assert any(i.code == "BENEFIT_REVIEW" for i in snapshot.issues)


def test_supported_codes_and_invalid_codes_are_distinguished():
    review = supplied_rows("EMP-0004", "EMP-0005", "EMP-0012", "EMP-0009", "EMP-0016")
    assert build_snapshot(review).valid
    correct(review, "9", {"AA": "ZZ"}, "Test unknown code")
    snapshot = build_snapshot(review)
    assert any(i.code == "INVALID_CODE" and i.severity == "error" for i in snapshot.issues)
    assert not snapshot.valid


def test_missing_derived_totals_are_computed_but_bad_totals_are_not_repaired():
    review = load_reference("validated")
    correct(review, "6", {"I": "", "L": "", "O": "", "S": ""}, "Exercise blank computed fields")
    snapshot = build_snapshot(review)
    assert snapshot.valid
    assert snapshot.records[0].amount("I") == Decimal("82187.50")
    assert snapshot.records[0].amount("O") == Decimal("449812.50")
    assert len([m for m in snapshot.mappings if m.code == "TOTALS"]) == 3
    assert review.source.rows[0].values["I"] == "82187.5"
    correct(review, "6", {"O": "1.00"}, "Exercise inconsistent supplied total")
    snapshot = build_snapshot(review)
    assert not snapshot.valid
    assert snapshot.records[0].amount("O") == Decimal("1.00")
    assert any(i.code == "ARITHMETIC" for i in snapshot.issues)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("V", "000-000-000-0000", "EMPLOYEE_TIN"),
        ("W", "Reyes\nSantos", "NAME_CONTROL"),
        ("W", "Reyes 漢", "NAME_ENCODING"),
        ("C", "2025-02-30", "EMPLOYMENT_DATE"),
        ("F", "", "AMOUNT"),
    ],
)
def test_candidate_policy_never_ignores_real_errors(field, value, code):
    review = load_reference("validated")
    correct(review, "6", {field: value}, "Test genuinely invalid input")
    snapshot = build_snapshot(review)
    assert any(i.code == code and i.severity == "error" for i in snapshot.issues)
    assert not snapshot.valid
    with pytest.raises(ValueError, match="blocked"):
        serialize(snapshot)


def test_original_workbook_is_still_blocked_without_any_partial_output():
    snapshot = build_snapshot(load_reference("workbook"))
    assert len(snapshot.records) == 11
    assert {(i.field, i.row_key) for i in snapshot.issues if i.severity == "error"} == {
        ("tin", ""),
        ("branch", ""),
        ("V", "12"),
    }
    with pytest.raises(ValueError, match="blocked"):
        serialize(snapshot)
