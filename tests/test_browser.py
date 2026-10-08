"""Workspace interaction checks. Run with ALPHALIST_BROWSER=chromium (or executable path)."""

import os
import socket
import threading
import time

import pytest
import uvicorn

from alphalist.domain import WORKBOOK
from alphalist.web import app

pytestmark = pytest.mark.skipif(
    not os.getenv("ALPHALIST_BROWSER"), reason="Browser checks are opt-in"
)


@pytest.fixture(scope="module")
def browser_server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            assert server.started
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)


@pytest.fixture
def page(browser_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        executable = os.environ["ALPHALIST_BROWSER"]
        browser = playwright.chromium.launch(
            **({"executable_path": executable} if executable != "chromium" else {})
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900}, base_url=browser_server
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        yield page
        browser.close()
        assert not errors


def import_workbook(page):
    from playwright.sync_api import expect

    page.goto("/")
    page.locator("#workbook").set_input_files(WORKBOOK)
    page.locator('[data-upload] button[type="submit"]').click()
    expect(page.locator("#attention-title")).to_have_text("3 fields to complete")
    expect(page.locator("[data-record]:visible")).to_have_count(10)


def test_workspace_corrections_search_drawer_downloads(page, tmp_path):
    from playwright.sync_api import expect

    import_workbook(page)
    page.screenshot(path=str(tmp_path / "workspace-desktop.png"), full_page=True)
    fifth = page.locator("[data-record]:visible").nth(4).bounding_box()
    assert fifth["y"] + fifth["height"] <= 900
    save = page.locator('button:has-text("Save details")').bounding_box()
    assert save["y"] + save["height"] <= 900
    expect(page.locator("#notification")).to_contain_text("Workbook prepared.")
    page.locator("#notification button").click()
    page.locator(".pdf-menu summary").click()
    expect(page.locator(".disabled-option")).to_contain_text("Final PDF")
    with page.expect_download() as draft:
        page.get_by_role("link", name="Draft PDF").click()
    assert draft.value.suggested_filename == "alphalist-draft.pdf"
    page.keyboard.press("Escape")
    page.locator("#next-page").click()
    expect(page.locator("[data-record]:visible")).to_have_count(1)
    page.locator("#employee-search").fill("EMP-0003")
    expect(page.locator("[data-record]:visible")).to_have_count(1)
    page.locator("#employee-search").fill("")
    page.locator("#employee-filter").select_option("attention")
    expect(page.locator("[data-record]:visible")).to_have_count(1)
    page.locator("#employee-filter").select_option("all")
    expect(page.locator("[data-record]:visible")).to_have_count(10)

    page.locator('a.issue-link[href="#field-tin"]').click()
    expect(page.locator('[name="value_tin"]')).to_be_focused()
    page.locator('[name="value_tin"]').fill("123456789")
    expect(page.locator("#export-status")).to_have_text("Save your changes before downloading.")
    page.locator('a.issue-link[href="#field-branch"]').click()
    expect(page.locator('[name="value_branch"]')).to_be_focused()
    page.locator('[name="value_branch"]').fill("0000")
    page.get_by_role("button", name="Save details").click()
    expect(page.locator("#attention-title")).to_have_text("1 field to complete")

    page.locator("#issues [data-employee]").click()
    expect(page.locator("#employee-drawer")).to_be_visible()
    expect(page.locator('[name="employee_tin"]')).to_be_focused()
    page.locator('[name="employee_tin"]').fill("987654321")
    page.keyboard.press("Escape")
    expect(page.locator("#confirm-dialog")).to_be_visible()
    page.get_by_role("button", name="Keep editing").click()
    expect(page.locator('[name="employee_tin"]')).to_have_value("987654321")
    for _ in range(15):
        page.keyboard.press("Tab")
        assert page.evaluate(
            "document.querySelector('#employee-drawer').contains(document.activeElement)"
        )
    page.locator('[name="employee_branch"]').fill("0000")
    page.get_by_role("button", name="Save changes").click()
    expect(page.locator("#attention-title")).to_have_text("Ready to export")
    expect(page.locator("#employee-drawer")).not_to_be_visible()
    expect(page.locator(".summary-card")).to_contain_text("4,100,331.50")
    expect(page.locator(".summary-card")).to_contain_text("423,857.50")
    page.locator("[data-open-totals]").click()
    expect(page.locator("#totals-dialog")).to_be_visible()
    page.locator(".changes summary").click()
    expect(page.locator(".history-item")).to_have_count(3)
    page.keyboard.press("Escape")
    expect(page.locator("[data-open-totals]")).to_be_focused()
    with page.expect_download() as download:
        page.locator('[href="/download/dat"]').click()
    assert download.value.suggested_filename.endswith(".DAT")


def test_failed_requests_and_responsive_focus(page, tmp_path):
    from playwright.sync_api import expect

    import_workbook(page)
    page.locator("#notification button").click()
    page.locator("#issues [data-employee]").click()
    page.locator('[name="employee_tin"]').fill("123")
    page.get_by_role("button", name="Save changes").click()
    expect(page.locator("#employee-drawer")).to_be_visible()
    expect(page.locator('[name="employee_tin"]')).to_have_value("123")
    expect(page.locator('[name="employee_tin"]')).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#employee-drawer")).not_to_be_visible()
    page.locator('[name="value_tin"]').fill("123456789")
    page.route(
        "**/correct/context",
        lambda route: route.fulfill(
            status=503, content_type="application/json", body='{"detail":"Try again."}'
        ),
    )
    page.get_by_role("button", name="Save details").click()
    expect(page.locator("#employer .form-error")).to_have_text("Try again.")
    expect(page.locator('[name="value_tin"]')).to_have_value("123456789")
    expect(page.locator("#export-status")).to_have_text("Save your changes before downloading.")
    page.unroute("**/correct/context")
    page.locator('[name="value_tin"]').fill("")

    for width in (1024, 720, 390, 320):
        page.set_viewport_size({"width": width, "height": 900})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if width == 390:
            page.screenshot(path=str(tmp_path / "workspace-mobile.png"), full_page=True)
            page.locator("#issues [data-employee]").click()
            assert page.locator("#employee-drawer").bounding_box()["width"] == width
            page.keyboard.press("Escape")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.locator(".nav-import").click()
    page.locator("#workbook").set_input_files(
        {"name": "bad.xlsx", "mimeType": "application/octet-stream", "buffer": b"bad"}
    )
    page.locator('[data-upload] button[type="submit"]').click()
    expect(page.locator("#confirm-dialog")).to_be_visible()
    page.locator('[data-confirm="yes"]').click()
    expect(page.locator("[data-upload] .form-error")).to_be_visible()
    expect(page.locator("#file-name")).to_have_text("bad.xlsx")
    page.get_by_role("link", name="Continue review").click()
    expect(page.locator("#attention-title")).to_have_text("3 fields to complete")


def test_original_and_export_spellings_can_be_searched_and_reviewed(page):
    from playwright.sync_api import expect

    import_workbook(page)
    page.locator("#notification button").click()
    for search, original, exported in (
        ("nunez", "Ñunez, Ana Liza Cruz", "NUNEZ, ANA LIZA CRUZ"),
        ("ñunez", "Ñunez, Ana Liza Cruz", "NUNEZ, ANA LIZA CRUZ"),
        ("obrien-santos", "O'Brien-Santos, Mark Anthony Villar", "OBRIEN-SANTOS, MARK ANTHONY VILLAR"),
    ):
        page.locator("#employee-search").fill(search)
        row = page.locator("[data-record]:visible")
        expect(row).to_have_count(1)
        expect(row).to_contain_text(original)
        expect(row).to_contain_text(f"Export: {exported}")
        row.locator("[data-employee]").click()
        expect(page.locator("#employee-title")).to_have_text(original)
        expect(page.locator("#employee-drawer .notice")).to_contain_text(f"Export name: {exported}")
        page.keyboard.press("Escape")
        expect(page.locator("#employee-drawer")).not_to_be_visible()
