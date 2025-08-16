"""
Browser-based testing using Playwright

This test file uses Playwright to test JavaScript functionality in real browsers.
Tests homepage vertical tabs behavior that requires DOM manipulation and click events.

Requirements:
- pip install playwright
- playwright install firefox  (or chromium, webkit)

Usage:
- Default (Firefox): pytest tests/test_browser.py
- Chromium: PLAYWRIGHT_BROWSER=chromium pytest tests/test_browser.py
- WebKit: PLAYWRIGHT_BROWSER=webkit pytest tests/test_browser.py
"""

from abiflib import get_abiftool_dir
import os
import pytest
import re
import subprocess
import tempfile
import time
from urllib.parse import quote

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


@pytest.fixture(scope="session")
def browser_name():
    """Allow browser selection via environment variable"""
    return os.environ.get('PLAYWRIGHT_BROWSER', 'firefox')


@pytest.fixture(scope="session")
def browser(browser_name):
    """Launch browser for testing"""
    if sync_playwright is None:
        pytest.skip("Playwright is required for browser tests. Install with: pip install playwright")

    with sync_playwright() as p:
        if browser_name == 'chromium':
            browser = p.chromium.launch(headless=True)
        elif browser_name == 'firefox':
            browser = p.firefox.launch(headless=True)
        elif browser_name == 'webkit':
            browser = p.webkit.launch(headless=True)
        else:
            raise ValueError(f"Unsupported browser: {browser_name}")

        yield browser
        browser.close()


@pytest.fixture(scope="session")
def awt_server():
    """Start awt.py server for testing (similar to test_routes.py)"""
    awt_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    abiftool_dir = get_abiftool_dir()

    env = os.environ.copy()
    env['AWT_DIR'] = awt_dir
    env['ABIFTOOL_DIR'] = abiftool_dir
    env['PYTHONUNBUFFERED'] = '1'

    log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    log_path = log_file.name
    print(f"\n[pytest] Logging awt.py output to {log_path}")

    caching_backend = os.environ.get('AWT_PYTEST_CACHING', 'none')
    proc = subprocess.Popen(
        ['python3', os.path.join(awt_dir, 'awt.py'), f'--caching={caching_backend}'],
        stdout=open(log_path, 'w'),
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid
    )

    try:
        port = None
        for _ in range(30):  # Try for 6 seconds
            time.sleep(0.2)
            with open(log_path) as f:
                output = f.read()
            match = re.search(r'Running on http://127\.0\.0\.1:(\d+)', output)
            if match:
                port = int(match.group(1))
                break

        if port is None:
            raise RuntimeError(f"Failed to start awt.py server. Log: {log_path}")

        print(f"[pytest] awt.py server started on port {port}")
        yield f"http://127.0.0.1:{port}"

    finally:
        print(f"[pytest] Stopping awt.py server (PID {proc.pid})")
        os.killpg(os.getpgid(proc.pid), 9)
        proc.wait()
        os.unlink(log_path)


def test_homepage_tab_switching(browser, awt_server):
    """
    Test homepage vertical tabs

    This test demonstrates the current broken behavior where all tabs
    show their content simultaneously instead of only the active tab.
    """
    page = browser.new_page()

    try:
        # Navigate to homepage
        page.goto(f"{awt_server}/awt")

        # Wait for page to load
        page.wait_for_selector("ul.tab-links")

        # Check initial state
        active_contents = page.query_selector_all("div.tab-content.active")

        assert len(active_contents) == 1, f"Expected 1 active tab content, found {len(active_contents)}"

        # Test tab clicking behavior
        tabs = page.query_selector_all("ul.tab-links li")
        assert len(tabs) >= 5, "Should have at least 5 example tabs"

        # Click second tab
        second_tab = tabs[1]  # "TNexampleScores"
        second_tab.click()

        # Wait a moment for JavaScript to run
        page.wait_for_timeout(100)

        # Check that only the second tab content is active
        active_contents_after_click = page.query_selector_all("div.tab-content.active")
        assert len(active_contents_after_click) == 1, "Should have exactly 1 active tab after clicking"

        # Verify the correct content is shown
        active_content = active_contents_after_click[0]
        assert "example2" in active_content.get_attribute("id"), "Second tab content should be active"

    finally:
        page.close()


def test_homepage_tab_structure_exists(browser, awt_server):
    """
    Test that basic homepage structure exists (should pass even with broken JS)
    """
    page = browser.new_page()

    try:
        page.goto(f"{awt_server}/awt")
        page.wait_for_selector("ul.tab-links")

        # Check tab structure exists
        tab_links = page.query_selector("ul.tab-links")
        assert tab_links is not None, "Tab links container should exist"

        tabs = page.query_selector_all("ul.tab-links li")
        assert len(tabs) >= 5, "Should have multiple tab links"

        contents = page.query_selector_all("div.tab-content")
        assert len(contents) >= 5, "Should have multiple tab content areas"

        # Check that tabs have data-target attributes
        first_tab = tabs[0]
        target = first_tab.get_attribute("data-target")
        assert target is not None, "Tabs should have data-target attributes"

        # Check corresponding content exists
        target_content = page.query_selector(f"div#{target}")
        assert target_content is not None, f"Content area with id='{target}' should exist"

    finally:
        page.close()


@pytest.mark.parametrize("dummy", [None], ids=["browser_debug"])
def test_debug_tab_state(dummy, browser, awt_server):
    """Debug helper to inspect current tab state"""
    page = browser.new_page()

    try:
        page.goto(f"{awt_server}/awt")
        page.wait_for_selector("ul.tab-links")

        print("\n=== Browser Tab State Debug ===")

        tabs = page.query_selector_all("ul.tab-links li")
        print(f"Total tabs: {len(tabs)}")

        for i, tab in enumerate(tabs):
            target = tab.get_attribute("data-target")
            text = tab.inner_text()[:50]
            print(f"Tab {i}: target='{target}' text='{text}'")

        contents = page.query_selector_all("div.tab-content")
        print(f"Total content areas: {len(contents)}")

        active_contents = page.query_selector_all("div.tab-content.active")
        print(f"Active content areas: {len(active_contents)}")

        for i, content in enumerate(active_contents):
            content_id = content.get_attribute("id")
            print(f"Active content {i}: id='{content_id}'")

        print("================================\n")

    finally:
        page.close()
