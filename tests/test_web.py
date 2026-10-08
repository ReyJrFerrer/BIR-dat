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
    assert "Ready for BIR validation" in response.text
    assert client.get("/download/dat").content == REFERENCE.read_bytes()
    assert client.get("/download/pdf").headers["content-type"] == "application/pdf"


def test_resolution_screen_prioritizes_only_real_corrections(client):
    _, response = load(client, "workbook")
    assert "3 fields" in response.text
    assert "Optional review questions" in response.text
    assert "Automatic preparation" in response.text
    assert "Lossless candidate encoding" in response.text
    assert "92 blockers" not in response.text
    response = client.get("/employee/12")
    assert response.status_code == 200
    main_fields = response.text.split("CORRECT THESE FIRST")[1].split("</section>")[0]
    assert 'name="value_V"' in main_fields
    assert 'name="value_J"' not in main_fields
    assert "Other employee details" in response.text
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
            "reason": "Testing shared review",
        },
    )
    assert response.status_code == 200
    audit = client.get("/download/audit").json()
    assert audit["filing_declarations"]["prior"] == "none"
    assert audit["effective_declarations"]["10"]["prior"] == "present"
    assert audit["corrections"][0]["scope"] == "filing"
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
    assert "Ready for BIR validation" in response.text
    assert "Download DAT for validation" in response.text
    assert "Previous evidence does not validate this current review" in response.text
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
