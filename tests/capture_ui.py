from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT = Path(".artifacts")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def capture() -> None:
    OUTPUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=EDGE)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(5000)
        page.goto("http://localhost:8501", wait_until="domcontentloaded")
        page.locator(".teams-topbar").wait_for(state="visible")
        page.wait_for_timeout(1500)
        page.screenshot(path=OUTPUT / "teams-desktop.png", full_page=True)

        sidebar_test_ids = page.locator('[data-testid*="Sidebar"]').evaluate_all(
            "elements => [...new Set(elements.map(element => element.dataset.testid))]"
        )
        print(f"Sidebar controls: {sidebar_test_ids}", flush=True)
        page.get_by_test_id("stSidebarHeader").hover()
        page.get_by_test_id("stSidebarCollapseButton").click(timeout=5000)
        collapsed_test_ids = page.locator('[data-testid]').evaluate_all(
            "elements => [...new Set(elements.map(element => element.dataset.testid))].filter(value => /sidebar|collapse/i.test(value))"
        )
        print(f"Collapsed controls: {collapsed_test_ids}", flush=True)
        reopen = page.get_by_test_id("stExpandSidebarButton")
        reopen.wait_for(state="visible")
        page.wait_for_timeout(700)
        page.screenshot(path=OUTPUT / "teams-sidebar-closed.png", full_page=True)
        reopen.click()
        page.get_by_test_id("stSidebar").wait_for(state="visible")
        page.get_by_text("Action tracker", exact=True).wait_for(state="visible")

        sidebar = page.get_by_test_id("stSidebar")
        sidebar.get_by_text("Meetings", exact=True).click()
        page.get_by_role("heading", name="Meetings", exact=True).wait_for()
        page.wait_for_timeout(500)
        page.screenshot(path=OUTPUT / "teams-meetings.png", full_page=True)

        page.get_by_role("tab", name="Manage meetings").click()
        page.get_by_label("Manage meetings").get_by_text(
            "AI assistant access", exact=True
        ).wait_for()
        page.wait_for_timeout(300)
        page.screenshot(path=OUTPUT / "teams-manage-meeting.png", full_page=True)

        sidebar.get_by_text("Action tracker", exact=True).click()
        page.get_by_role("heading", name="Action tracker", exact=True).wait_for()
        page.wait_for_timeout(300)
        page.screenshot(path=OUTPUT / "teams-actions.png", full_page=True)

        sidebar.get_by_text("Notifications", exact=True).click()
        page.get_by_role("heading", name="Notifications", exact=True).wait_for()
        page.wait_for_timeout(1200)
        page.screenshot(path=OUTPUT / "teams-notifications.png", full_page=True)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto("http://localhost:8501", wait_until="domcontentloaded")
        mobile.locator(".teams-topbar").wait_for(state="visible")
        mobile.wait_for_timeout(1500)
        mobile.screenshot(path=OUTPUT / "teams-mobile.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    capture()
