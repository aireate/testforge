import re

from playwright.sync_api import Locator, Page, expect


class ProductsPage:
    """商品管理页 Page Object。"""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.view = page.get_by_test_id("products-view")
        self.rows = page.get_by_test_id("product-row")
        self.total = page.get_by_test_id("product-total")
        self.search_input = page.get_by_test_id("search-input")
        self.search_submit = page.get_by_test_id("search-submit")
        self.reset_search = page.get_by_test_id("reset-search")
        self.create_panel = page.get_by_test_id("create-panel")
        self.toast = page.get_by_test_id("toast")
        self.logout = page.get_by_test_id("logout")
        self.current_user = page.get_by_test_id("current-user")

    def expect_loaded(self) -> "ProductsPage":
        expect(self.view).to_be_visible()
        expect(self.rows.first).to_be_visible()
        return self

    def row_count(self) -> int:
        return self.rows.count()

    def total_count(self) -> int:
        return int(self.total.inner_text())

    def row_by_name(self, name: str) -> Locator:
        return self.rows.filter(has_text=name)

    def search(self, keyword: str) -> None:
        self.search_input.fill(keyword)
        self.search_submit.click()

    def reset(self) -> None:
        self.reset_search.click()

    def create_product(self, name: str, price: str, stock: str, category: str = "数码") -> None:
        self.page.get_by_test_id("create-name").fill(name)
        self.page.get_by_test_id("create-price").fill(price)
        self.page.get_by_test_id("create-stock").fill(stock)
        self.page.get_by_test_id("create-category").select_option(label=category)
        self.page.get_by_test_id("create-submit").click()

    def delete_product(self, name: str) -> None:
        self.row_by_name(name).get_by_role("button", name="删除").click()

    def expect_toast(self, text: str | re.Pattern) -> None:
        expect(self.toast).to_have_text(text)
        expect(self.toast).to_have_class(re.compile(r"\bshow\b"))

    def expect_logged_in_as(self, username: str) -> None:
        expect(self.current_user).to_have_text(username)
