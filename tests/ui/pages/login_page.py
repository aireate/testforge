from playwright.sync_api import Page, expect


class LoginPage:
    """登录页 Page Object：元素定位与操作集中管理，用例只描述业务。"""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.username = page.get_by_test_id("username")
        self.password = page.get_by_test_id("password")
        self.submit = page.get_by_test_id("login-submit")
        self.error = page.get_by_test_id("login-error")
        self.view = page.get_by_test_id("login-view")

    def open(self) -> "LoginPage":
        self.page.goto(f"{self.base_url}/ui/login")
        expect(self.view).to_be_visible()
        return self

    def login(self, username: str, password: str) -> None:
        self.username.fill(username)
        self.password.fill(password)
        self.submit.click()

    def expect_error(self, message: str) -> None:
        expect(self.error).to_have_text(message)
