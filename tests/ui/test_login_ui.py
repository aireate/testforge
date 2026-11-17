import allure
import pytest
from playwright.sync_api import expect

from tests.ui.pages.login_page import LoginPage
from tests.ui.pages.products_page import ProductsPage

pytestmark = [pytest.mark.ui]


@allure.epic("UI 自动化")
@allure.feature("登录页")
class TestLoginUI:
    @allure.title("登录页渲染出账号、密码与提交按钮")
    @pytest.mark.smoke
    def test_login_page_renders(self, page, ui_settings):
        login_page = LoginPage(page, ui_settings.base_url).open()
        expect(login_page.username).to_be_visible()
        expect(login_page.password).to_be_visible()
        expect(login_page.submit).to_be_visible()
        expect(page.get_by_text("演示账号")).to_be_visible()

    @allure.title("管理员通过 UI 登录后进入商品页")
    @pytest.mark.smoke
    def test_admin_login_success(self, page, ui_settings, login):
        login(ui_settings.admin_username, ui_settings.admin_password)
        products = ProductsPage(page, ui_settings.base_url)
        products.expect_loaded()
        products.expect_logged_in_as("admin")
        expect(products.create_panel).to_be_visible()

    @allure.title("密码错误时展示错误提示且停留在登录页")
    def test_login_wrong_password(self, page, ui_settings):
        login_page = LoginPage(page, ui_settings.base_url).open()
        login_page.login(ui_settings.admin_username, "wrong-password")
        login_page.expect_error("用户名或密码错误")
        expect(login_page.view).to_be_visible()
        expect(page.get_by_test_id("products-view")).to_be_hidden()

    @allure.title("普通用户登录后看不到新增/删除入口")
    def test_user_cannot_see_admin_controls(self, page, ui_settings, login):
        login(ui_settings.user_username, ui_settings.user_password)
        products = ProductsPage(page, ui_settings.base_url)
        products.expect_loaded()
        products.expect_logged_in_as("user")
        expect(products.create_panel).to_be_hidden()
        expect(page.get_by_role("button", name="删除")).to_have_count(0)
