import uuid

from api.coupon_api import CouponApi
from api.order_api import OrderApi
from common.db_util import DbUtil
from common.request_util import RequestUtil


def _stock(db: DbUtil, product_id: int) -> int:
    return int(db.scalar("SELECT stock FROM products WHERE id = ?", (product_id,)))


def test_admin_can_create_coupon(coupon_factory) -> None:
    coupon = coupon_factory(type="fixed", value=3000, total_quantity=50)
    assert coupon["code"].startswith("CP")
    assert coupon["type"] == "fixed"
    assert coupon["value"] == 3000
    assert coupon["claimed_quantity"] == 0


def test_normal_user_cannot_create_coupon(user_client: RequestUtil) -> None:
    response = CouponApi(user_client).create(
        code=f"CP{uuid.uuid4().hex[:8].upper()}", value=1000
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_claim_coupon_success(user_client: RequestUtil, coupon_factory) -> None:
    coupon = coupon_factory()
    response = CouponApi(user_client).claim(coupon["code"])
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unused"
    assert data["coupon"]["code"] == coupon["code"]

    mine = CouponApi(user_client).mine().json()
    assert any(item["coupon"]["code"] == coupon["code"] for item in mine)


def test_claim_same_coupon_twice_is_rejected(
    user_client: RequestUtil, coupon_factory
) -> None:
    coupon = coupon_factory()
    api = CouponApi(user_client)
    assert api.claim(coupon["code"]).status_code == 200
    response = api.claim(coupon["code"])
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_ALREADY_CLAIMED"


def test_claim_sold_out_coupon(
    user_client: RequestUtil, admin_client: RequestUtil, coupon_factory
) -> None:
    coupon = coupon_factory(total_quantity=1)
    assert CouponApi(user_client).claim(coupon["code"]).status_code == 200
    response = CouponApi(admin_client).claim(coupon["code"])
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_SOLD_OUT"


def test_claim_expired_coupon(user_client: RequestUtil, coupon_factory) -> None:
    coupon = coupon_factory(
        valid_from="2020-01-01T00:00:00", valid_to="2020-01-31T00:00:00"
    )
    response = CouponApi(user_client).claim(coupon["code"])
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_EXPIRED"


def test_coupon_invalid_percent_is_rejected(admin_client: RequestUtil) -> None:
    response = CouponApi(admin_client).create(
        code=f"CP{uuid.uuid4().hex[:8].upper()}", type="percent", value=110
    )
    assert response.status_code == 422


def test_order_applies_fixed_discount(
    user_client: RequestUtil, coupon_factory, product_factory
) -> None:
    product = product_factory(price_cents=19900, stock=10)
    coupon = coupon_factory(type="fixed", value=3000)
    CouponApi(user_client).claim(coupon["code"])

    response = OrderApi(user_client).create(
        [{"product_id": product["id"], "quantity": 1}],
        coupon_code=coupon["code"],
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["subtotal_cents"] == 19900
    assert order["discount_cents"] == 3000
    assert order["total_cents"] == 16900
    assert order["coupon_code"] == coupon["code"]


def test_order_applies_percent_discount(
    user_client: RequestUtil, coupon_factory, product_factory
) -> None:
    product = product_factory(price_cents=10000, stock=10)
    coupon = coupon_factory(type="percent", value=10)
    CouponApi(user_client).claim(coupon["code"])

    response = OrderApi(user_client).create(
        [{"product_id": product["id"], "quantity": 2}],
        coupon_code=coupon["code"],
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["subtotal_cents"] == 20000
    assert order["discount_cents"] == 2000
    assert order["total_cents"] == 18000


def test_coupon_min_spend_rolls_back_stock(
    user_client: RequestUtil, coupon_factory, product_factory, db: DbUtil
) -> None:
    product = product_factory(price_cents=19900, stock=10)
    coupon = coupon_factory(type="fixed", value=3000, min_spend_cents=50000)
    CouponApi(user_client).claim(coupon["code"])
    before = _stock(db, product["id"])

    response = OrderApi(user_client).create(
        [{"product_id": product["id"], "quantity": 1}],
        coupon_code=coupon["code"],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_MIN_SPEND"
    assert _stock(db, product["id"]) == before


def test_coupon_cannot_be_used_twice(
    user_client: RequestUtil, coupon_factory, product_factory
) -> None:
    product = product_factory(price_cents=19900, stock=10)
    coupon = coupon_factory(type="fixed", value=3000)
    api = CouponApi(user_client)
    api.claim(coupon["code"])
    order_api = OrderApi(user_client)
    first = order_api.create(
        [{"product_id": product["id"], "quantity": 1}], coupon_code=coupon["code"]
    )
    assert first.status_code == 201

    second = order_api.create(
        [{"product_id": product["id"], "quantity": 1}], coupon_code=coupon["code"]
    )
    assert second.status_code == 409
    assert second.json()["code"] == "COUPON_ALREADY_USED"


def test_cancel_order_restores_coupon_and_stock(
    user_client: RequestUtil, coupon_factory, product_factory, db: DbUtil
) -> None:
    product = product_factory(price_cents=19900, stock=10)
    coupon = coupon_factory(type="fixed", value=3000)
    coupon_api = CouponApi(user_client)
    coupon_api.claim(coupon["code"])
    order_api = OrderApi(user_client)
    order = order_api.create(
        [{"product_id": product["id"], "quantity": 2}], coupon_code=coupon["code"]
    ).json()
    assert _stock(db, product["id"]) == 8

    response = order_api.cancel(order["id"])
    assert response.status_code == 200
    assert _stock(db, product["id"]) == 10
    mine = coupon_api.mine().json()
    item = next(i for i in mine if i["coupon"]["code"] == coupon["code"])
    assert item["status"] == "unused"
    assert item["order_id"] is None


def test_unclaimed_coupon_is_rejected(
    user_client: RequestUtil, coupon_factory, product_factory
) -> None:
    product = product_factory(price_cents=19900, stock=10)
    coupon = coupon_factory()
    response = OrderApi(user_client).create(
        [{"product_id": product["id"], "quantity": 1}],
        coupon_code=coupon["code"],
    )
    assert response.status_code == 409
    assert response.json()["code"] == "COUPON_NOT_AVAILABLE"
