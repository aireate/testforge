import uuid

import allure
import pytest

from api.auth_api import AuthApi
from api.order_api import OrderApi
from api.product_api import ProductApi

pytestmark = [pytest.mark.api, pytest.mark.db]


@allure.epic("数据一致性")
@allure.feature("落库校验")
class TestDatabaseConsistency:
    @allure.title("创建订单后订单、明细、库存三方数据一致")
    @pytest.mark.smoke
    def test_order_persistence(self, admin_client, user_client, db, product_factory, order_factory):
        product = product_factory(stock=9, price_cents=12345)
        order = order_factory(items=[{"product_id": product["id"], "quantity": 2}])

        row = db.query_one(
            "SELECT user_id, status, total_cents FROM orders WHERE id = ?", (order["id"],)
        )
        assert row["status"] == "created"
        assert row["total_cents"] == 24690

        items = db.query_all(
            "SELECT product_id, quantity, unit_price_cents FROM order_items WHERE order_id = ?",
            (order["id"],),
        )
        assert len(items) == 1
        assert items[0]["product_id"] == product["id"]
        assert items[0]["quantity"] == 2
        assert items[0]["unit_price_cents"] == 12345

        assert db.scalar("SELECT stock FROM products WHERE id = ?", (product["id"],)) == 7

        user_id = AuthApi(user_client).me().json()["id"]
        assert row["user_id"] == user_id

    @allure.title("取消订单后状态与库存同时更新")
    def test_cancel_persistence(self, admin_client, user_client, db, product_factory):
        product = product_factory(stock=4)
        order = OrderApi(user_client).create(
            [{"product_id": product["id"], "quantity": 3}]
        ).json()

        OrderApi(user_client).cancel(order["id"])

        assert db.scalar("SELECT status FROM orders WHERE id = ?", (order["id"],)) == "cancelled"
        assert db.scalar("SELECT stock FROM products WHERE id = ?", (product["id"],)) == 4

    @allure.title("幂等记录持久化，且响应体与首次下单结果一致")
    def test_idempotency_record_persisted(self, user_client, db, product_factory):
        product = product_factory(stock=6)
        key = f"idem-{uuid.uuid4().hex}"
        api = OrderApi(user_client)
        items = [{"product_id": product["id"], "quantity": 2}]

        order = api.create(items, idempotency_key=key).json()
        replay = api.create(items, idempotency_key=key)

        record = db.query_one(
            "SELECT response_code, response_body FROM idempotency_records WHERE idem_key = ?",
            (key,),
        )
        assert record["response_code"] == 201
        assert f'"id": {order["id"]}' in record["response_body"]
        assert replay.headers["X-Idempotent-Replay"] == "true"

        api.cancel(order["id"])

    @allure.title("商品创建与删除在库中真实生效")
    def test_product_persistence(self, admin_client, db):
        name = f"落库校验-{uuid.uuid4().hex[:6]}"
        created = ProductApi(admin_client).create(
            {
                "name": name,
                "description": "db check",
                "price_cents": 500,
                "stock": 2,
                "category": "测试",
            }
        ).json()
        assert db.count("products", "name = ?", (name,)) == 1

        ProductApi(admin_client).delete(created["id"])
        assert db.count("products", "name = ?", (name,)) == 0

    @allure.title("订单状态流转持久化：shipped -> completed")
    def test_status_transition_persistence(self, admin_client, db, order_factory):
        order = order_factory()
        OrderApi(admin_client).ship(order["id"])
        assert db.scalar("SELECT status FROM orders WHERE id = ?", (order["id"],)) == "shipped"

        OrderApi(admin_client).complete(order["id"])
        assert db.scalar("SELECT status FROM orders WHERE id = ?", (order["id"],)) == "completed"

    @allure.title("用户密码以 PBKDF2 哈希存储，不是明文")
    def test_password_is_hashed(self, db):
        rows = db.query_all("SELECT username, password_hash FROM users")
        assert len(rows) >= 2
        for row in rows:
            assert row["password_hash"].startswith("pbkdf2_sha256$")
            assert "admin123" not in row["password_hash"]
            assert "user123" not in row["password_hash"]

    @allure.title("订单操作后数据库无外键违规")
    def test_foreign_key_integrity(self, user_client, db, product_factory, order_factory):
        product = product_factory(stock=5)
        order_factory(items=[{"product_id": product["id"], "quantity": 1}])
        assert db.foreign_key_violations() == []

    @allure.title("并发下单后明细总数与扣减库存相等")
    def test_concurrent_stock_consistency(self, settings, user_token, db, product_factory):
        from concurrent.futures import ThreadPoolExecutor

        from common.request_util import RequestUtil

        product = product_factory(stock=4)
        api_url = settings.api_base

        def buy():
            client = RequestUtil(base_url=api_url, token=user_token)
            return OrderApi(client).create(
                [{"product_id": product["id"], "quantity": 1}]
            ).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(lambda _: buy(), range(4)))

        assert codes.count(201) == 4
        total_qty = db.scalar(
            "SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE product_id = ?",
            (product["id"],),
        )
        assert total_qty == 4
        assert db.scalar("SELECT stock FROM products WHERE id = ?", (product["id"],)) == 0
