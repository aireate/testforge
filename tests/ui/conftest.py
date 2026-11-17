import os
from pathlib import Path

import allure
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from config.settings import Settings, settings as base_settings


@pytest.fixture(scope="session")
def playwright_instance():
    instance = sync_playwright().start()
    yield instance
    instance.stop()


@pytest.fixture(scope="session")
def browser(playwright_instance) -> Browser:
    channel = os.getenv("TESTFORGE_BROWSER_CHANNEL", "msedge")
    headless = os.getenv("TESTFORGE_HEADED", "0") != "1"
    launch_options = {"headless": headless}
    if channel and channel != "bundled":
        launch_options["channel"] = channel
    browser = playwright_instance.chromium.launch(**launch_options)
    yield browser
    browser.close()


@pytest.fixture
def context(browser: Browser, tmp_path: Path) -> BrowserContext:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
    yield ctx
    trace_path = tmp_path / "trace.zip"
    ctx.tracing.stop(path=str(trace_path))
    if trace_path.exists():
        try:
            allure.attach.file(
                str(trace_path), name="Playwright Trace", extension="zip"
            )
        except Exception:  # pragma: no cover
            pass
    ctx.close()


@pytest.fixture
def page(context: BrowserContext) -> Page:
    return context.new_page()


@pytest.fixture
def ui_settings(sut_server) -> Settings:
    from dataclasses import replace

    return replace(base_settings, base_url=sut_server.base_url)


@pytest.fixture
def login(page: Page, ui_settings: Settings):
    from tests.ui.pages.login_page import LoginPage

    def _login(username: str, password: str):
        login_page = LoginPage(page, ui_settings.base_url).open()
        login_page.login(username, password)
        return login_page

    return _login


@pytest.fixture
def admin_page(page: Page, ui_settings: Settings, login) -> Page:
    login(ui_settings.admin_username, ui_settings.admin_password)
    page.get_by_test_id("products-view").wait_for(state="visible")
    return page


@pytest.fixture
def user_page(page: Page, ui_settings: Settings, login) -> Page:
    login(ui_settings.user_username, ui_settings.user_password)
    page.get_by_test_id("products-view").wait_for(state="visible")
    return page


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    page = item.funcargs.get("page")
    if page is None:
        return
    try:
        allure.attach(
            page.screenshot(full_page=True),
            name="失败截图",
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception:  # pragma: no cover
        pass
