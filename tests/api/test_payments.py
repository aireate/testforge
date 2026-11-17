import uuid

from api.coupon_api import CouponApi
from api.order_api import OrderApi
from api.payment_api import PaymentApi
from common.db_util import DbUtil
from common.request_util import RequestUtil


def _trade_no() -> str:
    return f"TRADE{uuid.uuid4().hex[:12].upper()}"


def _create_order(user_client: RequestUtil, product_factory, **coupon_kwargs) -> dict:
    product = product_factory(price_cents=19900, stock=10)
    coupon_code = None
    if coupon_kwargs:
        coupon = coupon_kwargs["coupon"]
        CouponApi(user_client).claim(coupon["code"])
        coupon_code = coupon["code"]
    response = OrderApi(user_client).create(
        [{"product_id": product["id"], "quantity": 1}], coupon_code=coupon_code
    )
    assert response.status_code == 201, response.text
    return response.json()


def _pay(
    anonymous_client: RequestUtil,
    order: dict,
    amount: int | None = None,
    trade_no: str | None = None,
    signature: str | None = None,
    status: str = "success",
):
    payload = {
        "order_no": order["order_no"],
        "trade_no": trade_no or _trade_no(),
        "amount_cents": order["total_cents"] if amount is None else amount,
        "status": status,
    }
    return PaymentApi(anonymous_client).callback(payload, signature=signature)


def test_payment_callback_marks_order_paid(
    user_client: RequestUtil, anonymous_client: RequestUtil, product_factory, db: DbUtil
) -> None:
    order = _create_order(user_client, product_factory)
    response = _pay(anonymous_client, order)
    assert response.status_code == 200, response.text
    assert response.json()["order_status"] == "paid"

    row = db.query_one("SELECT status, paid_at FROM orders WHERE id = ?", (order["id"],))
    assert row["status"] == "paid"
    assert row["paid_at"] is not None
    assert db.count("payments", "order_id = ?", (order["id"],)) == 1


def test_payment_rejects_invalid_signature(
    user_client: RequestUtil, anonymous_client: RequestUtil, product_factory, db: DbUtil
) -> None:
    order = _create_order(user_client, product_factory)
    response = _pay(anonymous_client, order, signature="deadbeef")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_SIGNATURE"
    assert db.scalar("SELECT status FROM orders WHERE id = ?", (order["id"],)) == "created"


def test_payment_rejects_amount_mismatch(
    user_client: RequestUtil, anonymous_client: RequestUtil, product_factory, db: DbUtil
) -> None:
    order = _create_order(user_client, product_factory)
    response = _pay(anonymous_client, order, amount=order["total_cents"] + 1)
    assert response.status_code == 400
    assert response.json()["code"] == "PAYMENT_AMOUNT_MISMATCH"
    assert db.scalar("SELECT status FROM orders WHERE id = ?", (order["id"],)) == "created"


def test_duplicate_payment_callback_is_idempotent(
    user_client: RequestUtil, anonymous_client: RequestUtil, product_factory, db: DbUtil
) -> None:
    order = _create_order(user_client, product_factory)
    trade_no = _trade_no()
    first = _pay(anonymous_client, order, trade_no=trade_no)
    assert first.status_code == 200
    second = _pay(anonymous_client, order, trade_no=trade_no)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert db.count("payments", "order_id = ?", (order["id"],)) == 1


def test_payment_rejects_cancelled_order(
    user_client: RequestUtil, anonymous_client: RequestUtil, product_factory
) -> None:
    order = _create_order(user_client, product_factory)
    assert OrderApi(user_client).cancel(order["id"]).status_code == 200
    response = _pay(anonymous_client, order)
    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_STATE_INVALID"


def test_payment_unknown_order_returns_404(
    anonymous_client: RequestUtil,
) -> None:
    fake_order = {"order_no": "TF-NOT-EXIST", "total_cents": 100}
    response = _pay(anonymous_client, fake_order)
    assert response.status_code == 404
    assert response.json()["code"] == "ORDER_NOT_FOUND"


def test_refund_restores_stock_coupon_and_payment(
    user_client: RequestUtil,
    admin_client: RequestUtil,
    anonymous_client: RequestUtil,
    coupon_factory,
    product_factory,
    db: DbUtil,
) -> None:
    coupon = coupon_factory(type="fixed", value=3000)
    order = _create_order(user_client, product_factory, coupon=coupon)
    assert _pay(anonymous_client, order).status_code == 200
    assert db.scalar("SELECT stock FROM products WHERE id = ?", (order["items"][0]["product_id"],)) == 9

    response = OrderApi(admin_client).refund(order["id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "refunded"
    assert db.scalar("SELECT stock FROM products WHERE id = ?", (order["items"][0]["product_id"],)) == 10
    assert db.scalar("SELECT status FROM payments WHERE order_id = ?", (order["id"],)) == "refunded"
    mine = CouponApi(user_client).mine().json()
    item = next(i for i in mine if i["coupon"]["code"] == coupon["code"])
    assert item["status"] == "unused"


def test_normal_user_cannot_refund(
    user_client: RequestUtil, anonymous_client: RequestUtil, product_factory
) -> None:
    order = _create_order(user_client, product_factory)
    assert _pay(anonymous_client, order).status_code == 200
    response = OrderApi(user_client).refund(order["id"])
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_refund_unpaid_order_is_rejected(
    user_client: RequestUtil, admin_client: RequestUtil, product_factory
) -> None:
    order = _create_order(user_client, product_factory)
    response = OrderApi(admin_client).refund(order["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "ORDER_STATE_INVALID"
