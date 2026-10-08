import re

import pytest
from fastapi.testclient import TestClient

from alphalist.domain import REFERENCE, WORKBOOK
from alphalist.web import app, store


@pytest.fixture
def client():
    store.sessions.clear()
    with TestClient(app) as client:
        yield client


def token(client):
    return re.search(r'name="csrf" value="([^"]+)"', client.get("/").text)[1]


def load(client, kind):
    csrf = token(client)
    response = client.post(f"/reference/{kind}", data={"csrf": csrf})
    assert response.status_code == 200, response.text
    return csrf, response


def test_home_and_validated_download(client):
    _, response = load(client, "validated")
    assert "Ready to export" in response.text
    assert client.get("/download/dat").content == REFERENCE.read_bytes()
    assert client.get("/download/pdf").headers["content-type"] == "application/pdf"


def test_resolution_screen_prioritizes_only_real_corrections(client):
    _, response = load(client, "workbook")
    assert "3 fields" in response.text
    for removed in (
        "Optional review questions",
        "Optional source review",
        "Automatic preparation",
        "Official validation evidence",
        "Clear this review",
        "Download review record",
        'href="/download/audit"',
        'name="reason"',
        "<th>Rule</th>",
    ):
        assert removed not in response.text
    assert "Advanced options" in response.text
    assert "data-record" in response.text
    assert response.text.count("<tr data-record") == 11
    assert "92 blockers" not in response.text
    response = client.get("/employee/12")
    assert response.status_code == 200
    main_fields = response.text.split('class="required-fields"')[1].split("</section>")[0]
    assert 'name="employee_tin"' in main_fields
    assert 'name="employee_branch"' in main_fields
    assert 'name="value_J"' not in main_fields
    assert "Other details" in response.text
    assert 'name="reason"' not in response.text
    assert client.get("/download/dat").status_code == 400
    assert client.get("/download/pdf").status_code == 400
    assert client.get("/download/draft").status_code == 200


def test_shared_form_audit_and_stale_update(client):
    csrf, _ = load(client, "workbook")
    response = client.post(
        "/correct/filing",
        data={
            "csrf": csrf,
            "revision": "0",
            "value_prior": "none",
        },
    )
    assert response.status_code == 200
    audit = client.get("/download/audit").json()
    assert audit["filing_declarations"]["prior"] == "none"
    assert audit["effective_declarations"]["10"]["prior"] == "present"
    assert audit["corrections"][0]["scope"] == "filing"
    assert audit["corrections"][0]["reason"] == ""
    assert audit["corrections"][0]["timestamp"]
    assert client.get("/download/dat").status_code == 400
    stale = client.post(
        "/correct/filing",
        data={"csrf": csrf, "revision": "0", "value_prior": "unknown", "reason": "Stale update"},
    )
    assert stale.status_code == 409


def test_csrf_and_session_isolation(client):
    load(client, "validated")
    assert client.post("/correct/context", data={"csrf": "bad"}).status_code == 403
    with TestClient(app) as other:
        assert other.get("/download/dat").status_code == 404


def test_upload_and_invalid_xlsx(client):
    csrf = token(client)
    response = client.post(
        "/upload", data={"csrf": csrf}, files={"workbook": (WORKBOOK.name, WORKBOOK.read_bytes())}
    )
    assert response.status_code == 200
    assert len(client.get("/download/audit").json()["source_rows"]) == 11
    response = client.post("/upload", data={"csrf": csrf}, files={"workbook": ("bad.xlsx", b"bad")})
    assert response.status_code == 400


def test_candidate_download_enabled_with_review_notes_and_hash_invalidation(client):
    csrf, _ = load(client, "validated")
    response = client.post(
        "/correct/6",
        data={
            "csrf": csrf,
            "revision": "0",
            "value_withholding": "unknown",
            "value_AS": "28999.00",
            "reason": "Exercise candidate with a retained review note",
        },
    )
    assert response.status_code == 200
    assert "Ready to export" in response.text
    assert "Download DAT for validation" in response.text
    assert "Previous evidence does not validate this current review" not in response.text
    assert client.get("/download/dat").status_code == 200
    assert client.get("/download/pdf").status_code == 200
    record = client.get("/download/audit").json()
    assert record["blocking_issues"] == []
    assert record["review_notes"]
    assert record["automatic_mappings"]
    assert record["output_hash"] != record["evidence"]["dat_hash"]
    assert not record["evidence_matches_current_output"]


def test_encoding_selection_is_exposed_and_audited(client):
    csrf, _ = load(client, "validated")
    response = client.post(
        "/correct/context",
        data={
            "csrf": csrf,
            "revision": "0",
            "value_encoding": "utf-8",
            "reason": "Exercise explicit candidate encoding selection",
        },
    )
    assert response.status_code == 200
    assert client.get("/download/audit").json()["encoding"] == "utf-8"
    assert client.get("/download/dat").content == REFERENCE.read_bytes()  # ASCII fixture unchanged.


def test_reason_free_corrections_update_saved_snapshot_without_confirming_unknowns(client):
    csrf, response = load(client, "workbook")
    original = client.get("/download/audit").json()
    response = client.post(
        "/correct/context",
        data={
            "csrf": csrf,
            "revision": "0",
            "value_tin": "123456789",
            "value_branch": "0000",
        },
    )
    assert response.status_code == 200
    assert "1 field to complete" in response.text
    assert client.get("/download/dat").status_code == 400
    response = client.post(
        "/correct/12",
        data={
            "csrf": csrf,
            "revision": "1",
            "employee_tin": "987654321",
            "employee_branch": "0000",
        },
    )
    assert response.status_code == 200
    assert "Ready to export" in response.text
    assert client.get("/download/dat").status_code == 200
    assert client.get("/download/pdf").status_code == 200
    saved = client.get("/download/audit").json()
    assert saved["source_rows"] == original["source_rows"]
    assert saved["totals"] == original["totals"]
    assert saved["declarations"] == original["declarations"]
    assert saved["filing_declarations"] == original["filing_declarations"]
    assert len(saved["corrections"]) == 3
    assert all(c["reason"] == "" and c["timestamp"] for c in saved["corrections"])


def test_ajax_failed_import_preserves_review_and_invalid_save_keeps_blockers(client):
    csrf, _ = load(client, "validated")
    original = client.get("/download/audit").json()
    response = client.post(
        "/upload",
        data={"csrf": csrf},
        files={"workbook": ("bad.xlsx", b"bad")},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]
    assert client.get("/download/audit").json() == original
    response = client.post(
        "/correct/6",
        data={
            "csrf": csrf,
            "revision": "0",
            "employee_tin": "invalid",
            "employee_branch": "",
        },
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["redirect"] == "/review?employee=6#field-V"
    assert client.get("/download/dat").status_code == 400
    assert client.get("/download/pdf").status_code == 400
    assert client.get("/download/draft").status_code == 200


def test_employee_fragment_and_explicit_unsupported_decision(client):
    csrf, _ = load(client, "validated")
    client.post("/correct/6", data={"csrf": csrf, "revision": "0", "value_schedule": "mwe"})
    response = client.get("/employee/6?fragment=1")
    assert "<html" not in response.text
    assert 'name="value_schedule"' in response.text
    assert 'name="value_benefits"' not in response.text
    assert 'name="reason"' not in response.text
    assert client.get("/download/dat").status_code == 400
    assert client.get("/download/pdf").status_code == 400


def test_recheck_without_changes_does_not_claim_edits(client):
    csrf, _ = load(client, "validated")
    response = client.post("/correct/context", data={"csrf": csrf, "revision": "0"})
    assert "Review checked. Your files are ready to export." in response.text
    assert "Changes saved." not in response.text
    assert client.get("/download/audit").json()["corrections"] == []


def test_original_and_export_names_are_visible_in_shared_review_order(client):
    _, response = load(client, "workbook")
    assert "Export: NUNEZ, ANA LIZA CRUZ" in response.text
    assert "Export: OBRIEN-SANTOS, MARK ANTHONY VILLAR" in response.text
    assert response.text.index("EMP-0004</small>") < response.text.index("EMP-0012</small>")
    for key, original, exported in (
        ("9", "Ñunez, Ana Liza Cruz", "NUNEZ, ANA LIZA CRUZ"),
        ("13", "O&#39;Brien-Santos, Mark Anthony Villar", "OBRIEN-SANTOS, MARK ANTHONY VILLAR"),
    ):
        employee = client.get(f"/employee/{key}?fragment=1").text
        assert original in employee
        assert f"Export name: <strong>{exported}</strong>" in employee
        assert "Your original spelling is retained" in employee
    audit = client.get("/download/audit").json()
    assert audit["overrides"] == {} and audit["corrections"] == []
    assert {(m["before"], m["after"]) for m in audit["automatic_mappings"] if m["code"] == "NAME_NORMALIZATION"} == {
        ("Ñunez", "NUNEZ"), ("O'Brien-Santos", "OBRIEN-SANTOS")
    }


def test_unsupported_name_is_editable_and_blocks_exports_even_with_utf8(client):
    csrf, _ = load(client, "validated")
    response = client.post(
        "/correct/6",
        data={"csrf": csrf, "revision": "0", "value_X": "Maria &"},
    )
    assert response.status_code == 200
    for endpoint in ("/download/dat", "/download/pdf"):
        assert client.get(endpoint).status_code == 400
    assert client.get("/download/draft").status_code == 200
    employee = client.get("/employee/6").text
    required = employee.split('class="required-fields"')[1].split("</section>")[0]
    assert 'name="value_X"' in required
    assert "Unsupported export name character(s)" in required
    client.post(
        "/correct/context",
        data={"csrf": csrf, "revision": "1", "value_encoding": "utf-8"},
    )
    assert client.get("/download/dat").status_code == 400
    client.post("/correct/6", data={"csrf": csrf, "revision": "2", "value_X": "Maria"})
    assert client.get("/download/dat").content == REFERENCE.read_bytes()
    assert client.get("/download/pdf").status_code == 200
