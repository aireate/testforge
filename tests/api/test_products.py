import uuid

import allure
import pytest

from api.order_api import OrderApi
from api.product_api import ProductApi

pytestmark = [pytest.mark.api, pytest.mark.product]


@allure.epic("商品模块")
@allure.feature("商品列表")
class TestProductList:
    @allure.title("默认分页返回第一页 10 条")
    @pytest.mark.smoke
    def test_default_pagination(self, admin_client, db):
        response = ProductApi(admin_client).list()
        assert response.status_code == 200
        body = response.json()

        expected_total = db.count("products")
        assert body["total"] == expected_total
        assert body["page"] == 1
        assert body["size"] == 10
        assert body["pages"] == (expected_total + 9) // 10
        assert len(body["items"]) == min(10, expected_total)

    @allure.title("分页边界：末页不足一页、超出范围返回空列表")
    def test_pagination_boundaries(self, admin_client, product_factory):
        category = f"分页-{uuid.uuid4().hex[:6]}"
        for _ in range(4):
            product_factory(category=category)
        api = ProductApi(admin_client)

        first = api.list(page=1, size=3, category=category).json()
        assert first["total"] == 4
        assert first["pages"] == 2
        assert len(first["items"]) == 3

        second = api.list(page=2, size=3, category=category).json()
        assert len(second["items"]) == 1

        out_of_range = api.list(page=3, size=3, category=category).json()
        assert out_of_range["items"] == []

    @allure.title("非法分页参数返回 422")
    @pytest.mark.parametrize(
        "params",
        [{"page": 0}, {"size": 0}, {"size": 51}, {"page": "abc"}],
        ids=["page-zero", "size-zero", "size-too-large", "page-not-int"],
    )
    def test_invalid_pagination(self, admin_client, params):
        response = ProductApi(admin_client).list(**params)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    @allure.title("关键字命中商品名称并正确分页")
    def test_keyword_filter(self, admin_client):
        response = ProductApi(admin_client).list(keyword="键盘")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        for item in body["items"]:
            assert "键盘" in item["name"] or "键盘" in item["description"]

    @allure.title("关键字无匹配时返回空列表且 pages 为 0")
    def test_keyword_no_match(self, admin_client):
        body = ProductApi(admin_client).list(keyword=f"不存在-{uuid.uuid4().hex}").json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["pages"] == 0

    @allure.title("分类过滤只返回该分类商品")
    def test_category_filter(self, admin_client):
        body = ProductApi(admin_client).list(category="配件", size=50).json()
        assert body["total"] == 3
        assert all(item["category"] == "配件" for item in body["items"])

    @allure.title("in_stock 过滤与库存字段一致")
    @pytest.mark.parametrize("in_stock", [True, False], ids=["in-stock", "out-of-stock"])
    def test_in_stock_filter(self, admin_client, db, in_stock):
        body = ProductApi(admin_client).list(in_stock=in_stock, size=50).json()
        expected = db.count("products", "stock > 0" if in_stock else "stock = 0")
        assert body["total"] == expected
        for item in body["items"]:
            assert (item["stock"] > 0) is in_stock

    @allure.title("按价格升序 / 降序排序")
    @pytest.mark.parametrize("sort", ["price_asc", "price_desc"])
    def test_sort_by_price(self, admin_client, sort):
        body = ProductApi(admin_client).list(sort=sort, size=50).json()
        prices = [item["price_cents"] for item in body["items"]]
        expected = sorted(prices, reverse=(sort == "price_desc"))
        assert prices == expected

    @allure.title("不支持的排序字段返回 422 INVALID_SORT")
    def test_invalid_sort(self, admin_client):
        response = ProductApi(admin_client).list(sort="drop_table")
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_SORT"

    @allure.title("组合筛选：分类 + 有货 + 价格升序")
    def test_combined_filters(self, admin_client):
        body = ProductApi(admin_client).list(
            category="数码", in_stock=True, sort="price_asc", size=50
        ).json()
        prices = [item["price_cents"] for item in body["items"]]
        assert body["total"] == 4
        assert prices == sorted(prices)
        assert all(item["category"] == "数码" and item["stock"] > 0 for item in body["items"])


@allure.epic("商品模块")
@allure.feature("商品详情")
class TestProductDetail:
    @allure.title("查询存在的商品返回完整字段")
    def test_get_existing(self, admin_client):
        response = ProductApi(admin_client).get(1)
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert {"id", "name", "description", "price_cents", "price", "stock", "category"} <= set(body)

    @allure.title("查询不存在的商品返回 404 PRODUCT_NOT_FOUND")
    def test_get_not_found(self, admin_client):
        response = ProductApi(admin_client).get(999999)
        assert response.status_code == 404
        body = response.json()
        assert body["code"] == "PRODUCT_NOT_FOUND"
        assert "999999" in body["message"]

    @allure.title("商品 ID 类型非法返回 422")
    def test_get_invalid_id(self, admin_client):
        response = ProductApi(admin_client).get("abc")
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    @allure.title("price 字段与 price_cents 保持一致")
    def test_price_consistency(self, admin_client):
        for item in ProductApi(admin_client).list(size=50).json()["items"]:
            assert item["price"] == round(item["price_cents"] / 100, 2)


@allure.epic("商品模块")
@allure.feature("商品创建")
class TestProductCreate:
    @allure.title("管理员创建商品成功并落库")
    @pytest.mark.smoke
    def test_create_as_admin(self, admin_client, db):
        name = f"自动化测试商品-{uuid.uuid4().hex[:6]}"
        payload = {
            "name": name,
            "description": "接口创建",
            "price_cents": 2599,
            "stock": 7,
            "category": "测试",
        }
        response = ProductApi(admin_client).create(payload)
        assert response.status_code == 201
        body = response.json()

        assert body["name"] == name
        assert body["price_cents"] == 2599
        assert body["price"] == 25.99
        assert body["stock"] == 7

        row = db.query_one("SELECT * FROM products WHERE id = ?", (body["id"],))
        assert row is not None
        assert row["name"] == name
        assert row["price_cents"] == 2599

        cleanup = ProductApi(admin_client).delete(body["id"])
        assert cleanup.status_code == 204

    @allure.title("description 缺省时写入空字符串")
    def test_create_with_default_description(self, admin_client):
        payload = {
            "name": f"无描述商品-{uuid.uuid4().hex[:6]}",
            "price_cents": 100,
            "stock": 0,
            "category": "测试",
        }
        response = ProductApi(admin_client).create(payload)
        assert response.status_code == 201
        assert response.json()["description"] == ""
        ProductApi(admin_client).delete(response.json()["id"])

    @allure.title("普通用户创建商品返回 403")
    def test_create_as_user_forbidden(self, user_client):
        response = ProductApi(user_client).create(
            {
                "name": "user 不该创建成功",
                "price_cents": 100,
                "stock": 1,
                "category": "测试",
            }
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    @allure.title("未登录创建商品返回 401")
    def test_create_anonymous(self, anonymous_client):
        response = ProductApi(anonymous_client).create(
            {"name": "anonymous", "price_cents": 100, "stock": 1, "category": "测试"}
        )
        assert response.status_code == 401

    @allure.title("非法商品参数被校验拦截")
    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "A", "price_cents": 100, "stock": 1, "category": "测试"},
            {"name": "正常名称", "price_cents": 0, "stock": 1, "category": "测试"},
            {"name": "正常名称", "price_cents": -1, "stock": 1, "category": "测试"},
            {"name": "正常名称", "price_cents": 100, "stock": -1, "category": "测试"},
            {"name": "正常名称", "price_cents": 100, "stock": 1, "category": " "},
            {"price_cents": 100, "stock": 1, "category": "测试"},
        ],
        ids=["short-name", "zero-price", "negative-price", "negative-stock", "blank-category", "missing-name"],
    )
    def test_create_validation(self, admin_client, payload):
        response = ProductApi(admin_client).create(payload)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


@allure.epic("商品模块")
@allure.feature("商品更新")
class TestProductUpdate:
    @allure.title("管理员更新名称与价格成功并落库")
    @pytest.mark.smoke
    def test_update_fields(self, admin_client, db, product_factory):
        product = product_factory()
        new_name = f"已更新-{uuid.uuid4().hex[:6]}"
        response = ProductApi(admin_client).update(
            product["id"], {"name": new_name, "price_cents": 8888}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == new_name
        assert body["price_cents"] == 8888

        row = db.query_one("SELECT name, price_cents FROM products WHERE id = ?", (product["id"],))
        assert row["name"] == new_name
        assert row["price_cents"] == 8888

    @allure.title("仅更新库存，其他字段保持不变")
    def test_partial_update(self, admin_client, product_factory):
        product = product_factory(stock=5)
        response = ProductApi(admin_client).update(product["id"], {"stock": 99})
        assert response.status_code == 200
        body = response.json()
        assert body["stock"] == 99
        assert body["name"] == product["name"]
        assert body["price_cents"] == product["price_cents"]

    @allure.title("更新不存在的商品返回 404")
    def test_update_not_found(self, admin_client):
        response = ProductApi(admin_client).update(999999, {"name": "ghost"})
        assert response.status_code == 404
        assert response.json()["code"] == "PRODUCT_NOT_FOUND"

    @allure.title("普通用户更新商品返回 403")
    def test_update_as_user_forbidden(self, user_client, admin_client, product_factory):
        product = product_factory()
        response = ProductApi(user_client).update(product["id"], {"price_cents": 1})
        assert response.status_code == 403

    @allure.title("空对象更新不改变任何字段")
    def test_update_empty_payload(self, admin_client, product_factory):
        product = product_factory()
        response = ProductApi(admin_client).update(product["id"], {})
        assert response.status_code == 200
        assert response.json()["name"] == product["name"]
        assert response.json()["price_cents"] == product["price_cents"]

    @allure.title("更新时价格非法返回 422")
    def test_update_invalid_price(self, admin_client, product_factory):
        product = product_factory()
        response = ProductApi(admin_client).update(product["id"], {"price_cents": 0})
        assert response.status_code == 422


@allure.epic("商品模块")
@allure.feature("库存变更")
class TestStockChange:
    @allure.title("增加库存成功")
    def test_increase_stock(self, admin_client, db, product_factory):
        product = product_factory(stock=10)
        response = ProductApi(admin_client).change_stock(product["id"], 5)
        assert response.status_code == 200
        assert response.json()["stock"] == 15
        assert db.scalar("SELECT stock FROM products WHERE id = ?", (product["id"],)) == 15

    @allure.title("扣减库存成功")
    def test_decrease_stock(self, admin_client, product_factory):
        product = product_factory(stock=10)
        response = ProductApi(admin_client).change_stock(product["id"], -4)
        assert response.status_code == 200
        assert response.json()["stock"] == 6

    @allure.title("库存扣减不能为负，返回 409 且库存不变")
    def test_decrease_below_zero(self, admin_client, db, product_factory):
        product = product_factory(stock=3)
        response = ProductApi(admin_client).change_stock(product["id"], -4)
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "STOCK_NEGATIVE"
        assert body["details"]["current_stock"] == 3
        assert db.scalar("SELECT stock FROM products WHERE id = ?", (product["id"],)) == 3

    @allure.title("库存正好扣到 0 允许")
    def test_decrease_to_zero(self, admin_client, product_factory):
        product = product_factory(stock=2)
        response = ProductApi(admin_client).change_stock(product["id"], -2)
        assert response.status_code == 200
        assert response.json()["stock"] == 0

    @allure.title("普通用户变更库存返回 403")
    def test_change_stock_as_user(self, user_client, product_factory):
        product = product_factory()
        response = ProductApi(user_client).change_stock(product["id"], 1)
        assert response.status_code == 403


@allure.epic("商品模块")
@allure.feature("商品删除")
class TestProductDelete:
    @allure.title("删除商品返回 204，之后查询 404，数据库记录已删除")
    @pytest.mark.smoke
    def test_delete_product(self, admin_client, db, product_factory):
        product = product_factory()
        response = ProductApi(admin_client).delete(product["id"])
        assert response.status_code == 204

        assert ProductApi(admin_client).get(product["id"]).status_code == 404
        assert db.count("products", "id = ?", (product["id"],)) == 0

    @allure.title("删除不存在的商品返回 404")
    def test_delete_not_found(self, admin_client):
        response = ProductApi(admin_client).delete(999999)
        assert response.status_code == 404
        assert response.json()["code"] == "PRODUCT_NOT_FOUND"

    @allure.title("商品被订单引用时禁止删除，返回 409 PRODUCT_IN_USE")
    def test_delete_referenced_product(self, admin_client, user_client, product_factory):
        product = product_factory(stock=5)
        order = OrderApi(user_client).create([{"product_id": product["id"], "quantity": 1}])
        assert order.status_code == 201

        response = ProductApi(admin_client).delete(product["id"])
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "PRODUCT_IN_USE"
        assert body["details"]["order_item_count"] >= 1

    @allure.title("普通用户删除商品返回 403")
    def test_delete_as_user(self, user_client, product_factory):
        product = product_factory()
        response = ProductApi(user_client).delete(product["id"])
        assert response.status_code == 403
