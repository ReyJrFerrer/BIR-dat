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
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(render(snapshot))).pages)
    assert "3,825.00" in text and "573,800.00" in text
    assert "FOR BIR VALIDATION" in text
    assert "proof of payment" in text


def test_n_with_tilde_is_preserved_without_transliteration():
    review = supplied_rows("EMP-0004")
    snapshot = build_snapshot(review)
    output = serialize(snapshot)
    assert b"\xd1UNEZ" in output
    assert decoded_rows(snapshot)[1][8] == "ÑUNEZ"
    assert review.source.rows[0].values["W"] == "Ñunez"
    assert any(
        i.code == "CHARACTER_ACCEPTANCE" and i.severity == "warning" for i in snapshot.issues
    )
    correct(review, "context", {"encoding": "utf-8"}, "Test explicit lossless encoding selection")
    utf_snapshot = build_snapshot(review)
    assert "ÑUNEZ".encode() in serialize(utf_snapshot)
    assert serialize(utf_snapshot) != output
    verify(serialize(utf_snapshot), encoding="utf-8")


def test_embedded_quotes_and_commas_are_escaped_with_no_field_shift():
    review = load_reference("validated")
    correct(review, "6", {"W": 'Reyes, "Maria"'}, "Exercise reversible CSV quoting")
    snapshot = build_snapshot(review)
    assert snapshot.valid
    fields = decoded_rows(snapshot)[1]
    assert len(fields) == 49
    assert fields[8] == 'REYES, "MARIA"'
    assert b'"REYES, ""MARIA"""' in serialize(snapshot)
    assert any(i.code == "NAME_ESCAPING" for i in snapshot.issues)


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
