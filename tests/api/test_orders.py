import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import allure
import pytest

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi
from common.request_util import RequestUtil

pytestmark = [pytest.mark.api, pytest.mark.order]


def _stock(admin_client, product_id: int) -> int:
    return ProductApi(admin_client).get(product_id).json()["stock"]


@allure.epic("订单模块")
@allure.feature("下单")
class TestCreateOrder:
    @allure.title("单商品下单成功：金额、明细、库存均正确")
    @pytest.mark.smoke
    def test_create_single_item(self, admin_client, user_client, db, product_factory, order_factory):
        product = product_factory(stock=10, price_cents=19900)
        order = order_factory(items=[{"product_id": product["id"], "quantity": 2}])

        assert order["status"] == "created"
        assert order["order_no"].startswith("TF")
        assert order["total_cents"] == 39800
        assert len(order["items"]) == 1
        item = order["items"][0]
        assert item["product_id"] == product["id"]
        assert item["quantity"] == 2
        assert item["unit_price_cents"] == 19900
        assert item["subtotal_cents"] == 39800

        assert _stock(admin_client, product["id"]) == 8
        row = db.query_one("SELECT status, total_cents FROM orders WHERE id = ?", (order["id"],))
        assert row["status"] == "created"
        assert row["total_cents"] == 39800

    @allure.title("多商品下单金额为各明细之和")
    def test_create_multi_items(self, user_client, product_factory, order_factory):
        first = product_factory(stock=5, price_cents=1000)
        second = product_factory(stock=5, price_cents=250)
        order = order_factory(
            items=[
                {"product_id": first["id"], "quantity": 3},
                {"product_id": second["id"], "quantity": 4},
            ]
        )
        assert order["total_cents"] == 3 * 1000 + 4 * 250
        assert len(order["items"]) == 2

    @allure.title("库存不足返回 409 OUT_OF_STOCK，库存与订单均不变")
    def test_insufficient_stock(self, admin_client, user_client, db, product_factory):
        product = product_factory(stock=1)
        response = OrderApi(user_client).create(
            [{"product_id": product["id"], "quantity": 2}]
        )
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "OUT_OF_STOCK"
        assert body["details"] == {
            "product_id": product["id"],
            "requested": 2,
            "available": 1,
        }
        assert _stock(admin_client, product["id"]) == 1
        assert db.count("order_items", "product_id = ?", (product["id"],)) == 0

    @allure.title("购买不存在的商品返回 404 PRODUCT_NOT_FOUND")
    def test_product_not_found(self, user_client):
        response = OrderApi(user_client).create([{"product_id": 999999, "quantity": 1}])
        assert response.status_code == 404
        assert response.json()["code"] == "PRODUCT_NOT_FOUND"

    @allure.title("库存正好买完允许下单")
    def test_buy_exact_stock(self, admin_client, product_factory, order_factory):
        product = product_factory(stock=3)
        order = order_factory(items=[{"product_id": product["id"], "quantity": 3}])
        assert order["total_cents"] == product["price_cents"] * 3
        assert _stock(admin_client, product["id"]) == 0

    @allure.title("非法下单参数被校验拦截")
    @pytest.mark.parametrize(
        "items",
        [
            [],
            [{"product_id": 1, "quantity": 0}],
            [{"product_id": 1, "quantity": 1000}],
            [{"product_id": 1, "quantity": 1}, {"product_id": 1, "quantity": 2}],
            [{"quantity": 1}],
        ],
        ids=["empty", "zero-quantity", "quantity-over-limit", "duplicate-product", "missing-product-id"],
    )
    def test_validation(self, user_client, items):
        response = OrderApi(user_client).create(items)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    @allure.title("未登录下单返回 401")
    def test_anonymous(self, anonymous_client):
        response = OrderApi(anonymous_client).create([{"product_id": 1, "quantity": 1}])
        assert response.status_code == 401


@allure.epic("订单模块")
@allure.feature("幂等控制")
class TestIdempotency:
    @allure.title("相同 Idempotency-Key 重复提交只创建一单")
    @pytest.mark.smoke
    def test_replay_returns_same_order(self, admin_client, user_client, db, product_factory):
        product = product_factory(stock=10)
        key = f"idem-{uuid.uuid4().hex}"
        api = OrderApi(user_client)
        items = [{"product_id": product["id"], "quantity": 2}]

        first = api.create(items, idempotency_key=key)
        second = api.create(items, idempotency_key=key)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        assert second.headers.get("X-Idempotent-Replay") == "true"
        assert _stock(admin_client, product["id"]) == 8
        assert (
            db.count(
                "order_items",
                "product_id = ?",
                (product["id"],),
            )
            == 1
        )
        api.cancel(first.json()["id"])

    @allure.title("同一 Key 提交不同内容返回 409 IDEMPOTENCY_CONFLICT")
    def test_key_conflict_with_different_payload(self, user_client, product_factory):
        product = product_factory(stock=10)
        key = f"idem-{uuid.uuid4().hex}"
        api = OrderApi(user_client)

        first = api.create([{"product_id": product["id"], "quantity": 1}], idempotency_key=key)
        assert first.status_code == 201
        second = api.create([{"product_id": product["id"], "quantity": 2}], idempotency_key=key)
        assert second.status_code == 409
        assert second.json()["code"] == "IDEMPOTENCY_CONFLICT"
        api.cancel(first.json()["id"])

    @allure.title("不同用户使用相同 Key 互不影响")
    def test_key_is_scoped_by_user(self, admin_client, user_client, db, product_factory):
        product = product_factory(stock=10)
        key = f"idem-{uuid.uuid4().hex}"
        items = [{"product_id": product["id"], "quantity": 1}]

        admin_order = OrderApi(admin_client).create(items, idempotency_key=key)
        user_order = OrderApi(user_client).create(items, idempotency_key=key)

        assert admin_order.status_code == 201
        assert user_order.status_code == 201
        assert admin_order.json()["id"] != user_order.json()["id"]
        assert db.count("idempotency_records", "idem_key = ?", (key,)) == 2

        OrderApi(admin_client).cancel(admin_order.json()["id"])
        OrderApi(user_client).cancel(user_order.json()["id"])

    @allure.title("不传 Key 时每次提交都会创建新订单")
    def test_without_key_creates_new_orders(self, user_client, db, product_factory):
        product = product_factory(stock=10)
        api = OrderApi(user_client)
        items = [{"product_id": product["id"], "quantity": 1}]

        first = api.create(items)
        second = api.create(items)
        assert first.json()["id"] != second.json()["id"]
        assert second.headers.get("X-Idempotent-Replay") is None

        api.cancel(first.json()["id"])
        api.cancel(second.json()["id"])


@allure.epic("订单模块")
@allure.feature("订单查询")
class TestQueryOrder:
    @allure.title("下单后可查询到自己的订单")
    def test_get_own_order(self, user_client, order_factory):
        order = order_factory()
        response = OrderApi(user_client).get(order["id"])
        assert response.status_code == 200
        assert response.json()["id"] == order["id"]
        assert response.json()["status"] == "created"

    @allure.title("普通用户查询他人订单返回 403")
    def test_get_others_order_forbidden(self, user_client, admin_client, order_factory):
        other_order = order_factory(client=admin_client)
        response = OrderApi(user_client).get(other_order["id"])
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    @allure.title("管理员可查询任意订单")
    def test_admin_can_get_any_order(self, admin_client, order_factory):
        order = order_factory()
        response = OrderApi(admin_client).get(order["id"])
        assert response.status_code == 200
        assert response.json()["id"] == order["id"]

    @allure.title("查询不存在的订单返回 404")
    def test_get_not_found(self, user_client):
        response = OrderApi(user_client).get(999999)
        assert response.status_code == 404
        assert response.json()["code"] == "ORDER_NOT_FOUND"

    @allure.title("订单 ID 非法返回 422")
    def test_get_invalid_id(self, user_client):
        response = OrderApi(user_client).get("abc")
        assert response.status_code == 422

    @allure.title("普通用户订单列表只包含自己的订单")
    def test_user_list_only_own(self, settings, user_client, db):
        user_id = AuthApi(user_client).me().json()["id"]
        body = OrderApi(user_client).list(size=50).json()
        assert body["total"] == db.count("orders", "user_id = ?", (user_id,))
        assert all(item["user_id"] == user_id for item in body["items"])

    @allure.title("管理员订单列表可看到所有用户订单")
    def test_admin_list_all(self, admin_client, db):
        body = OrderApi(admin_client).list(size=50).json()
        assert body["total"] == db.count("orders")
        assert len(body["items"]) == min(50, body["total"])

    @allure.title("按状态过滤订单")
    @pytest.mark.parametrize("status", ["created", "cancelled"])
    def test_filter_by_status(self, user_client, db, order_factory, status):
        order = order_factory()
        if status == "cancelled":
            OrderApi(user_client).cancel(order["id"])
        body = OrderApi(user_client).list(status=status, size=50).json()
        assert body["total"] >= 1
        assert all(item["status"] == status for item in body["items"])
        user_id = AuthApi(user_client).me().json()["id"]
        assert body["total"] == db.count(
            "orders", "user_id = ? AND status = ?", (user_id, status)
        )

    @allure.title("非法状态过滤返回 422 INVALID_STATUS")
    def test_filter_invalid_status(self, user_client):
        response = OrderApi(user_client).list(status="unknown")
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_STATUS"

    @allure.title("订单列表分页返回正确条数")
    def test_list_pagination(self, user_client, order_factory):
        for _ in range(3):
            order_factory()
        body = OrderApi(user_client).list(page=1, size=2).json()
        assert body["size"] == 2
        assert len(body["items"]) <= 2


@allure.epic("订单模块")
@allure.feature("订单状态流转")
class TestOrderLifecycle:
    @allure.title("取消订单后库存归还且状态为 cancelled")
    @pytest.mark.smoke
    def test_cancel_restores_stock(self, admin_client, user_client, db, product_factory):
        product = product_factory(stock=5)
        order = OrderApi(user_client).create(
            [{"product_id": product["id"], "quantity": 2}]
        ).json()
        assert _stock(admin_client, product["id"]) == 3

        response = OrderApi(user_client).cancel(order["id"])
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert _stock(admin_client, product["id"]) == 5
        assert db.scalar("SELECT status FROM orders WHERE id = ?", (order["id"],)) == "cancelled"

    @allure.title("重复取消返回 409 ORDER_STATE_INVALID")
    def test_cancel_twice(self, user_client, order_factory):
        order = order_factory()
        assert OrderApi(user_client).cancel(order["id"]).status_code == 200

        response = OrderApi(user_client).cancel(order["id"])
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "ORDER_STATE_INVALID"
        assert body["details"]["status"] == "cancelled"

    @allure.title("取消他人订单返回 403")
    def test_cancel_others_order(self, user_client, admin_client, order_factory):
        order = order_factory(client=admin_client)
        response = OrderApi(user_client).cancel(order["id"])
        assert response.status_code == 403

    @allure.title("管理员发货：created -> shipped")
    def test_ship_order(self, admin_client, order_factory):
        order = order_factory()
        response = OrderApi(admin_client).ship(order["id"])
        assert response.status_code == 200
        assert response.json()["status"] == "shipped"

    @allure.title("普通用户发货返回 403")
    def test_ship_as_user_forbidden(self, user_client, order_factory):
        order = order_factory()
        response = OrderApi(user_client).ship(order["id"])
        assert response.status_code == 403

    @allure.title("已取消订单不能发货")
    def test_ship_cancelled_order(self, admin_client, user_client, order_factory):
        order = order_factory()
        OrderApi(user_client).cancel(order["id"])
        response = OrderApi(admin_client).ship(order["id"])
        assert response.status_code == 409
        assert response.json()["code"] == "ORDER_STATE_INVALID"

    @allure.title("已发货订单不能取消")
    def test_cancel_shipped_order(self, admin_client, user_client, order_factory):
        order = order_factory()
        OrderApi(admin_client).ship(order["id"])
        response = OrderApi(user_client).cancel(order["id"])
        assert response.status_code == 409

    @allure.title("完整流转：created -> shipped -> completed")
    def test_complete_order(self, admin_client, order_factory):
        order = order_factory()
        assert OrderApi(admin_client).ship(order["id"]).json()["status"] == "shipped"

        response = OrderApi(admin_client).complete(order["id"])
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    @allure.title("未发货订单不能直接完成")
    def test_complete_created_order(self, admin_client, order_factory):
        order = order_factory()
        response = OrderApi(admin_client).complete(order["id"])
        assert response.status_code == 409

    @allure.title("普通用户完成订单返回 403")
    def test_complete_as_user_forbidden(self, user_client, admin_client, order_factory):
        order = order_factory()
        OrderApi(admin_client).ship(order["id"])
        response = OrderApi(user_client).complete(order["id"])
        assert response.status_code == 403


@allure.epic("订单模块")
@allure.feature("并发")
class TestConcurrency:
    @allure.title("并发抢购不超卖：库存 3，5 个并发请求恰好成功 3 单")
    def test_no_oversell_under_concurrency(self, settings, user_token, admin_client, db, product_factory):
        product = product_factory(stock=3)
        results: list[int] = []
        lock = threading.Lock()

        def place_order() -> None:
            client = RequestUtil(
                base_url=settings.api_base, timeout=settings.timeout, token=user_token
            )
            response = OrderApi(client).create(
                [{"product_id": product["id"], "quantity": 1}]
            )
            with lock:
                results.append(response.status_code)

        with ThreadPoolExecutor(max_workers=5) as pool:
            for _ in range(5):
                pool.submit(place_order)

        assert results.count(201) == 3, f"成功订单数异常: {results}"
        assert results.count(409) == 2, f"库存不足响应数异常: {results}"
        assert _stock(admin_client, product["id"]) == 0
        assert db.count("order_items", "product_id = ?", (product["id"],)) == 3
