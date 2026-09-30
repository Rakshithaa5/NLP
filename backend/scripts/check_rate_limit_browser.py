"""Isolated dashboard cooldown browser test with mocked HTTP responses; no Groq calls."""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from backend.scripts.test_semantic import meeting, controlled_response
from backend.services.semantic import analyze_transcript, GroqAnalyzer


def main():
    root = Path(__file__).resolve().parents[2]
    fixture = meeting()
    with patch.object(GroqAnalyzer, "request", return_value=controlled_response()):
        result = analyze_transcript(fixture["full_text"], fixture["segments"])
    ui = "http://127.0.0.1:5197"
    process = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5197", "--strictPort"],
        cwd=root / "frontend", stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        for _ in range(50):
            try:
                with urlopen(ui, timeout=1):
                    break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("Isolated Vite server exited")
                time.sleep(.1)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            errors, posts = [], []
            state = {"retry_at": 0}
            page.on("pageerror", lambda e: errors.append(str(e)))
            def api(route):
                if "/analysis/" not in route.request.url:
                    route.fulfill(json=fixture)
                elif route.request.method == "POST":
                    posts.append(route.request.url)
                    if len(posts) == 1:
                        state["retry_at"] = time.time() + 3
                        route.fulfill(status=429, headers={"Retry-After": "3", "Access-Control-Allow-Origin": "*", "Access-Control-Expose-Headers": "Retry-After"},
                                      json={"detail": "Groq rate limit reached."})
                    else:
                        state["retry_at"] = 0
                        route.fulfill(json=result)
                else:
                    attempt = {"state": "rate_limited", "retry_at": state["retry_at"], "message": "Groq rate limit reached."} if state["retry_at"] else None
                    route.fulfill(json={**result, "analysis_attempt": attempt})
            page.route("**/api/**", api)
            page.route("**/health", lambda route: route.fulfill(json={"status": "ok"}))
            page.goto(ui + "/dashboard/00000000-0000-0000-0000-000000000007")
            expect(page.get_by_role("heading", name="AI Meeting Summary")).to_be_visible()
            page.get_by_role("button", name="Re-analyse", exact=True).click()
            expect(page.get_by_text("Retry available in", exact=False)).to_be_visible()
            expect(page.get_by_role("button", name="Retry analysis", exact=True)).to_be_disabled()
            expect(page.get_by_role("button", name="Re-analyse", exact=True)).to_be_disabled()
            expect(page.get_by_role("button", name="Export PDF", exact=True)).to_be_enabled()
            expect(page.get_by_role("button", name="Retry loading", exact=True)).to_have_count(0)
            expect(page.get_by_role("heading", name="AI Meeting Summary")).to_be_visible()
            page.reload()
            expect(page.get_by_role("button", name="Retry analysis", exact=True)).to_be_disabled()
            expect(page.get_by_role("button", name="Retry analysis", exact=True)).to_be_enabled(timeout=7000)
            assert len(posts) == 1
            page.get_by_role("button", name="Retry analysis", exact=True).click()
            expect(page.get_by_role("alert")).to_have_count(0)
            assert len(posts) == 2 and not errors, (posts, errors)
            browser.close()
            print("PASS: cooldown, disabled retries, preserved report/export, reload, expiry and explicit retry; no Groq calls")
    finally:
        process.terminate()
        process.wait(timeout=10)

if __name__ == "__main__":
    main()
