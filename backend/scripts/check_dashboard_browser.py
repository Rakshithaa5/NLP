"""Run against local API/UI: python -m backend.scripts.check_dashboard_browser."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

API = os.getenv("TEST_API_URL", "http://127.0.0.1:8011")
UI = os.getenv("TEST_UI_URL", "http://127.0.0.1:5174")
FILE_ID = os.getenv("TEST_MEETING_ID", "0b11c60d-3dc0-4eaa-b8ba-9f7301fb692f")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Real local API; forwarding bypasses the dev proxy's default port 8000.
        def forward(route):
            parsed = urlsplit(route.request.url)
            response = route.fetch(url=API + parsed.path + ("?" + parsed.query if parsed.query else ""))
            route.fulfill(response=response)
        context.route("**/api/**", forward)
        result = context.request.post(API + "/api/analysis/" + FILE_ID, timeout=120000)
        assert result.ok, result.text()
        report = result.json()["intelligence"]
        print("Actual recording:", len(report["summary"]), "summary bullets;", len(report["decisions"]), "decisions;", len(report["questions"]), "questions")
        page.goto(UI + "/dashboard/" + FILE_ID)
        expect(page.get_by_role("heading", name="AI Meeting Summary")).to_be_visible(timeout=30000)
        expect(page.get_by_role("tab", name="Overview", exact=True)).to_have_attribute("aria-selected", "true")
        Path("data/validation").mkdir(exist_ok=True)
        page.screenshot(path="data/validation/dashboard-desktop.png", full_page=True)
        # Evidence must navigate to a real transcript segment.
        details = page.locator("details").filter(has=page.get_by_role("button", name="View transcript", exact=False, include_hidden=True)).first
        details.locator("summary").click()
        details.get_by_role("button", name="View transcript", exact=False).click()
        expect(page.get_by_role("tab", name="Transcript", exact=True)).to_have_attribute("aria-selected", "true")
        expect(page.locator(".mi-segment-selected")).to_be_visible()
        page.get_by_role("searchbox").fill("Wiley")
        assert page.locator(".mi-segment").count() > 0
        assert page.locator("mark").count() > 0
        page.get_by_role("searchbox").fill("a phrase absent from this recording 999")
        expect(page.get_by_text("No transcript segments match these filters.")).to_be_visible()
        page.get_by_role("searchbox").fill("")
        page.get_by_role("button", name="Decisions", exact=True).click()
        assert page.locator(".mi-segment").count() > 0
        page.reload()
        expect(page.get_by_role("searchbox")).to_be_visible(timeout=30000)
        page.get_by_role("tab", name="Analytics", exact=True).click()
        expect(page.get_by_text("Speaker analytics are unavailable.", exact=False)).to_be_visible()
        page.go_back()
        expect(page.get_by_role("searchbox")).to_be_visible()
        page.get_by_role("tab", name="Overview", exact=True).click()
        with page.expect_download() as download:
            page.get_by_role("button", name="Export PDF").click()
        assert download.value.failure() is None
        for width in (768, 390):
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"overflow at {width}"
            page.screenshot(path=f"data/validation/dashboard-{width}.png", full_page=True)
        # Explicit malformed-response fixtures test robustness, never product data.
        context.route("**/api/analysis/**", lambda route: route.fulfill(json={"intelligence": {"version": 2, "summary": [None, {}], "action_items": [None, {"task": {"bad": 1}}], "entities": {"people": [None, {}]}}, "classifications": None}))
        context.route("**/api/upload/**", lambda route: route.fulfill(json={"full_text": None, "segments": [None, {"text": {"bad": 1}, "speaker": {"bad": 1}}]}))
        page.reload()
        expect(page.get_by_text("No reliable summary is available yet.")).to_be_visible(timeout=30000)
        expect(page.get_by_text("Unassigned", exact=True)).to_be_visible()
        page.get_by_role("tab", name="Transcript", exact=True).click()
        expect(page.get_by_role("searchbox")).to_be_visible()
        page.get_by_role("tab", name="Analytics", exact=True).click()
        expect(page.get_by_role("heading", name="Meeting statistics")).to_be_visible()
        context.route("**/api/analysis/**", lambda route: route.fulfill(status=500, json={"detail": "Analysis service unavailable"}))
        page.reload()
        expect(page.get_by_role("alert").filter(has_text="Analysis service unavailable")).to_be_visible(timeout=30000)
        expect(page.get_by_role("button", name="Retry loading")).to_be_visible()
        assert not errors, errors
        browser.close()
        print("PASS: real API, Overview, evidence jump, search, filters, refresh, back navigation, Analytics, PDF download, tablet/mobile overflow, malformed payloads.")

if __name__ == "__main__": main()
