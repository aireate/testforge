import re
import uuid

import allure
import pytest
from playwright.sync_api import expect

from tests.ui.pages.products_page import ProductsPage

pytestmark = [pytest.mark.ui]


@allure.epic("UI 自动化")
@allure.feature("商品管理页")
class TestProductsUI:
    @allure.title("商品列表渲染，条数与总数一致")
    @pytest.mark.smoke
    def test_product_list_renders(self, admin_page, ui_settings):
        products = ProductsPage(admin_page, ui_settings.base_url)
        products.expect_loaded()
        total = products.total_count()
        assert total >= 10
        assert products.row_count() == total
        expect(products.row_by_name("机械键盘 K870")).to_have_count(1)

    @allure.title("关键字搜索只保留匹配行，重置后恢复全量")
    def test_search_and_reset(self, admin_page, ui_settings):
        products = ProductsPage(admin_page, ui_settings.base_url)
        products.expect_loaded()
        baseline = products.total_count()

        products.search("键盘")
        expect(products.rows).to_have_count(1)
        expect(products.row_by_name("键盘")).to_have_count(1)

        products.reset()
        expect(products.rows).to_have_count(baseline)

    @allure.title("通过 UI 新增商品后出现在列表，并清理数据")
    def test_create_product(self, admin_page, ui_settings):
        products = ProductsPage(admin_page, ui_settings.base_url)
        products.expect_loaded()
        baseline = products.total_count()
        name = f"UI新增-{uuid.uuid4().hex[:6]}"

        try:
            products.create_product(name, "99.50", "3", category="配件")
            products.expect_toast(f"已添加商品：{name}")
            expect(products.rows).to_have_count(baseline + 1)
            expect(products.row_by_name(name)).to_have_count(1)
            expect(products.row_by_name(name)).to_contain_text("￥99.50")
            assert products.total_count() == baseline + 1
        finally:
            if products.row_by_name(name).count():
                products.delete_product(name)

    @allure.title("通过 UI 删除商品后列表移除该行")
    def test_delete_product(self, admin_page, ui_settings):
        products = ProductsPage(admin_page, ui_settings.base_url)
        products.expect_loaded()
        baseline = products.total_count()
        name = f"UI待删-{uuid.uuid4().hex[:6]}"

        products.create_product(name, "12.30", "1", category="数码")
        expect(products.row_by_name(name)).to_have_count(1)

        products.delete_product(name)
        products.expect_toast(re.compile(r"已删除商品 #\d+"))
        expect(products.row_by_name(name)).to_have_count(0)
        expect(products.rows).to_have_count(baseline)
        assert products.total_count() == baseline

    @allure.title("退出登录后回到登录页并清除会话")
    def test_logout(self, admin_page, ui_settings):
        products = ProductsPage(admin_page, ui_settings.base_url)
        products.expect_loaded()
        products.logout.click()

        expect(admin_page.get_by_test_id("login-view")).to_be_visible()
        expect(admin_page.get_by_test_id("products-view")).to_be_hidden()
        assert admin_page.evaluate("() => localStorage.getItem('tf_token')") is None

        admin_page.reload()
        expect(admin_page.get_by_test_id("login-view")).to_be_visible()

    @allure.title("普通用户直接访问商品页仍可浏览但无写入口")
    def test_user_readonly_view(self, user_page, ui_settings):
        products = ProductsPage(user_page, ui_settings.base_url)
        products.expect_loaded()
        expect(products.create_panel).to_be_hidden()
        expect(user_page.get_by_role("button", name="删除")).to_have_count(0)
