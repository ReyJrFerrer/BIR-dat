import re

from fastapi.testclient import TestClient

from alphalist import web
from alphalist.domain import WORKBOOK


def test_browser_session_survives_separate_requests_without_server_storage(monkeypatch):
    web.store.sessions.clear()
    monkeypatch.setattr(web, "HOSTED", True)
    monkeypatch.setattr(web, "UPLOAD_LIMIT", 4 * 1024 * 1024)
    monkeypatch.setitem(web.templates.env.globals, "browser_mode", True)
    with TestClient(web.app) as client:
        assert "/static/boot.js" in client.get("/").text
        page = client.post("/browser/page", json={"path": "/", "state": None}).json()
        csrf = re.search(r'name="csrf" value="([^"]+)"', page["html"])[1]
        assert 'data-browser-session="true"' in page["html"]
        assert "up to 4 MB" in page["html"]
        assert "alphalist_session" not in client.cookies
        uploaded = client.post(
            "/upload",
            data={"csrf": csrf, "_browser_session": page["state"]},
            files={"workbook": (WORKBOOK.name, WORKBOOK.read_bytes())},
            headers={"Accept": "application/json"},
        ).json()
        assert uploaded["redirect"] == "/review"
        assert not web.store.sessions
        review = client.post(
            "/browser/page", json={"path": "/review", "state": uploaded["state"]}
        ).json()
        assert "3 fields to complete" in review["html"]
        employee = client.post(
            "/browser/page",
            json={"path": "/employee/12?fragment=1", "state": review["state"]},
        ).json()
        assert "<html" not in employee["html"]
        assert 'name="employee_tin"' in employee["html"]
        corrected = client.post(
            "/correct/filing",
            data={
                "csrf": csrf,
                "revision": "0",
                "value_prior": "none",
                "_browser_session": review["state"],
            },
            headers={"Accept": "application/json"},
        ).json()
        assert corrected["redirect"].startswith("/review")
        audit = client.post(
            "/browser/download/audit", json={"state": corrected["state"]}
        ).json()
        assert audit["filing_declarations"]["prior"] == "none"
        assert client.get("/download/audit").status_code == 404
        assert not web.store.sessions


def test_hosted_rejects_oversize_upload_request(monkeypatch):
    monkeypatch.setattr(web, "HOSTED", True)
    monkeypatch.setattr(web, "UPLOAD_LIMIT", 4 * 1024 * 1024)
    with TestClient(web.app) as client:
        response = client.post("/upload", headers={"content-length": str(5 * 1024 * 1024)})
        assert response.status_code == 413
