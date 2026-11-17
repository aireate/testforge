import uuid

import allure
import pytest

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi

pytestmark = [pytest.mark.api, pytest.mark.contract]


def _assert_error_envelope(body: dict, expected_code: str | None = None) -> None:
    assert set(body) == {"code", "message", "details"}
    assert isinstance(body["code"], str) and body["code"]
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["details"], dict)
    if expected_code:
        assert body["code"] == expected_code


@allure.epic("契约校验")
@allure.feature("健康检查")
class TestHealth:
    @allure.title("/healthz 返回服务与数据库状态")
    @pytest.mark.smoke
    def test_healthz(self, settings, anonymous_client):
        response = anonymous_client.get(f"{settings.base_url}/healthz")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert body["version"]


@allure.epic("契约校验")
@allure.feature("错误响应")
class TestErrorContract:
    @allure.title("404 响应符合统一错误结构")
    def test_404_envelope(self, admin_client):
        response = ProductApi(admin_client).get(999999)
        assert response.status_code == 404
        _assert_error_envelope(response.json(), "PRODUCT_NOT_FOUND")

    @allure.title("401 响应符合统一错误结构")
    def test_401_envelope(self, anonymous_client):
        response = anonymous_client.get("/auth/me")
        assert response.status_code == 401
        _assert_error_envelope(response.json(), "UNAUTHORIZED")

    @allure.title("403 响应符合统一错误结构")
    def test_403_envelope(self, user_client):
        response = ProductApi(user_client).create(
            {"name": "无权限创建", "price_cents": 100, "stock": 1, "category": "测试"}
        )
        assert response.status_code == 403
        _assert_error_envelope(response.json(), "FORBIDDEN")

    @allure.title("422 校验错误包含字段定位信息")
    def test_422_envelope(self, anonymous_client):
        response = anonymous_client.post("/auth/login", json_body={"username": "a"})
        assert response.status_code == 422
        body = response.json()
        _assert_error_envelope(body, "VALIDATION_ERROR")
        assert body["details"]["errors"]
        assert all("loc" in error and "msg" in error for error in body["details"]["errors"])

    @allure.title("未定义路由返回 404 JSON 而不是 HTML")
    def test_unknown_route(self, anonymous_client):
        response = anonymous_client.get("/not-exists")
        assert response.status_code == 404
        _assert_error_envelope(response.json(), "NOT_FOUND")

    @allure.title("不支持的方法返回 405 JSON")
    def test_method_not_allowed(self, anonymous_client):
        response = anonymous_client.patch("/auth/login", json_body={})
        assert response.status_code == 405
        _assert_error_envelope(response.json(), "HTTP_405")


@allure.epic("契约校验")
@allure.feature("响应结构")
class TestSchemaContract:
    @allure.title("登录响应字段与类型稳定")
    def test_login_schema(self, settings, anonymous_client):
        body = AuthApi(anonymous_client).login(
            settings.admin_username, settings.admin_password
        ).json()
        assert set(body) == {"access_token", "token_type", "expires_in", "user"}
        assert isinstance(body["access_token"], str)
        assert isinstance(body["expires_in"], int)
        assert set(body["user"]) == {"id", "username", "role"}
        assert isinstance(body["user"]["id"], int)

    @allure.title("商品分页结构字段与类型稳定")
    def test_product_page_schema(self, admin_client):
        body = ProductApi(admin_client).list(size=3).json()
        assert set(body) == {"items", "total", "page", "size", "pages"}
        for key in ("total", "page", "size", "pages"):
            assert isinstance(body[key], int)
        for item in body["items"]:
            assert set(item) == {
                "id",
                "name",
                "description",
                "price_cents",
                "price",
                "stock",
                "category",
            }
            assert isinstance(item["price"], float)
            assert isinstance(item["price_cents"], int)

    @allure.title("订单结构字段与明细类型稳定")
    def test_order_schema(self, user_client, order_factory):
        order = order_factory()
        body = OrderApi(user_client).get(order["id"]).json()
        assert set(body) == {"id", "order_no", "user_id", "status", "total_cents", "items"}
        assert isinstance(body["id"], int)
        assert isinstance(body["total_cents"], int)
        for item in body["items"]:
            assert set(item) == {
                "product_id",
                "product_name",
                "quantity",
                "unit_price_cents",
                "subtotal_cents",
            }

    @allure.title("响应不泄露密码等内部字段")
    def test_no_internal_fields(self, admin_client, product_factory):
        raw = ProductApi(admin_client).list(size=50).text.lower()
        assert "password" not in raw
        assert "password_hash" not in raw

    @allure.title("关键字中的 SQL 片段按字面量处理，不产生注入")
    def test_sql_injection_keyword(self, admin_client):
        payload = "' OR 1=1; DROP TABLE products;--"
        response = ProductApi(admin_client).list(keyword=payload)
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert ProductApi(admin_client).list(size=1).status_code == 200

    @allure.title("超长关键字被参数校验拦截")
    def test_keyword_too_long(self, admin_client):
        response = ProductApi(admin_client).list(keyword="x" * 51)
        assert response.status_code == 422

    @allure.title("中文与特殊字符关键字可正常查询")
    def test_unicode_keyword(self, admin_client):
        keyword = f"不存在的¥{uuid.uuid4().hex[:4]}"
        response = ProductApi(admin_client).list(keyword=keyword)
        assert response.status_code == 200
        assert response.json()["total"] == 0
