import json
import math
import secrets
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sut import faults
from sut.database import get_db
from sut.deps import get_current_user
from sut.errors import AppError
from sut.models import (
    Coupon,
    IdempotencyRecord,
    Order,
    OrderItem,
    Payment,
    Product,
    User,
    UserCoupon,
    utcnow,
    utcnow_naive,
)
from sut.schemas import OrderCreate, OrderOut, OrderPage
from sut.utils import to_order_out

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_STATUS = {
    "created",
    "paid",
    "shipped",
    "completed",
    "cancelled",
    "refunded",
}


def _order_or_404(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise AppError(404, "ORDER_NOT_FOUND", f"订单 {order_id} 不存在")
    return order


def _check_owner(order: Order, user: User) -> None:
    if faults.enabled("authz_missing"):
        return
    if user.role != "admin" and order.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "无权访问他人订单")


def _new_order_no() -> str:
    return f"TF{datetime.now(timezone.utc):%Y%m%d%H%M%S}{secrets.token_hex(2).upper()}"


def _request_hash(payload: OrderCreate) -> str:
    raw = json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _apply_coupon(
    db: Session, user: User, code: str, order: Order, subtotal: int
) -> int:
    user_coupon = db.scalar(
        select(UserCoupon)
        .join(Coupon, UserCoupon.coupon_id == Coupon.id)
        .where(UserCoupon.user_id == user.id, Coupon.code == code)
    )
    if user_coupon is None:
        raise AppError(409, "COUPON_NOT_AVAILABLE", "未领取该优惠券")

    coupon = user_coupon.coupon
    now = utcnow_naive()
    if now < coupon.valid_from or now > coupon.valid_to:
        raise AppError(409, "COUPON_EXPIRED", "优惠券不在有效期内")

    if user_coupon.status != "unused" and not faults.enabled("coupon_double_use"):
        raise AppError(409, "COUPON_ALREADY_USED", "优惠券已使用")

    if subtotal < coupon.min_spend_cents:
        raise AppError(
            409,
            "COUPON_MIN_SPEND",
            "未达到优惠券使用门槛",
            {"min_spend_cents": coupon.min_spend_cents, "subtotal_cents": subtotal},
        )

    if coupon.type == "fixed":
        discount = min(coupon.value, subtotal)
    else:
        discount = subtotal * coupon.value // 100
    if faults.enabled("discount_ignored"):
        discount = 0

    user_coupon.status = "used"
    user_coupon.order_id = order.id
    user_coupon.used_at = utcnow()
    order.coupon_id = coupon.id
    return discount


def _restore_coupon(db: Session, order: Order) -> None:
    user_coupon = db.scalar(
        select(UserCoupon).where(
            UserCoupon.order_id == order.id, UserCoupon.status == "used"
        )
    )
    if user_coupon is not None:
        user_coupon.status = "unused"
        user_coupon.order_id = None
        user_coupon.used_at = None


def _restore_stock(db: Session, order: Order) -> None:
    if faults.enabled("stock_not_restored"):
        return
    for item in order.items:
        db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock=Product.stock + item.quantity)
        )


def _build_order(db: Session, user: User, payload: OrderCreate) -> Order:
    order = Order(
        order_no=_new_order_no(),
        user_id=user.id,
        status="created",
        subtotal_cents=0,
        discount_cents=0,
        total_cents=0,
    )
    db.add(order)
    db.flush()

    subtotal = 0
    for item in payload.items:
        # 条件更新保证并发下单不会超卖
        statement = update(Product).where(Product.id == item.product_id)
        if not faults.enabled("stock_oversell"):
            statement = statement.where(Product.stock >= item.quantity)
        result = db.execute(
            statement.values(stock=Product.stock - item.quantity)
        )
        if result.rowcount == 0:
            db.rollback()
            product = db.get(Product, item.product_id)
            if product is None:
                raise AppError(
                    404, "PRODUCT_NOT_FOUND", f"商品 {item.product_id} 不存在"
                )
            raise AppError(
                409,
                "OUT_OF_STOCK",
                f"商品 {product.name} 库存不足",
                {
                    "product_id": product.id,
                    "requested": item.quantity,
                    "available": product.stock,
                },
            )
        product = db.get(Product, item.product_id)
        if faults.enabled("total_off_by_one"):
            subtotal += product.price_cents * item.quantity - 1
        else:
            subtotal += product.price_cents * item.quantity
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item.quantity,
                unit_price_cents=product.price_cents,
            )
        )

    discount = 0
    if payload.coupon_code:
        try:
            discount = _apply_coupon(
                db, user, payload.coupon_code, order, subtotal
            )
        except AppError:
            db.rollback()
            raise

    order.subtotal_cents = subtotal
    order.discount_cents = discount
    order.total_cents = max(0, subtotal - discount)
    db.commit()
    db.refresh(order)
    return order


@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request_hash = _request_hash(payload)

    if idempotency_key and not faults.enabled("idempotency_ignore"):
        existing = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user.id,
                IdempotencyRecord.idem_key == idempotency_key,
            )
        )
        if existing:
            if existing.request_hash != request_hash:
                raise AppError(
                    409,
                    "IDEMPOTENCY_CONFLICT",
                    "相同 Idempotency-Key 对应的请求内容不一致",
                )
            return Response(
                status_code=existing.response_code,
                content=existing.response_body,
                media_type="application/json",
                headers={"X-Idempotent-Replay": "true"},
            )

    order = _build_order(db, user, payload)
    body = json.dumps(to_order_out(db, order).model_dump(), ensure_ascii=False)

    if idempotency_key and not faults.enabled("idempotency_ignore"):
        record = IdempotencyRecord(
            user_id=user.id,
            idem_key=idempotency_key,
            request_hash=request_hash,
            response_code=201,
            response_body=body,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            # 并发同 key 请求：回滚本次订单，返回已存在结果
            db.rollback()
            existing = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.user_id == user.id,
                    IdempotencyRecord.idem_key == idempotency_key,
                )
            )
            if existing is None:
                raise
            return Response(
                status_code=existing.response_code,
                content=existing.response_body,
                media_type="application/json",
                headers={"X-Idempotent-Replay": "true"},
            )

    return Response(
        status_code=201, content=body, media_type="application/json"
    )


@router.get("", response_model=OrderPage)
def list_orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=50),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderPage:
    if status is not None and status not in ALLOWED_STATUS:
        raise AppError(422, "INVALID_STATUS", f"不支持的订单状态: {status}")

    stmt = select(Order)
    if user.role != "admin":
        stmt = stmt.where(Order.user_id == user.id)
    if status:
        stmt = stmt.where(Order.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    orders = db.scalars(
        stmt.order_by(Order.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return OrderPage(
        items=[to_order_out(db, o) for o in orders],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    order = _order_or_404(db, order_id)
    _check_owner(order, user)
    return to_order_out(db, order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    order = _order_or_404(db, order_id)
    _check_owner(order, user)
    if order.status != "created" and not faults.enabled("order_state_skip"):
        raise AppError(
            409,
            "ORDER_STATE_INVALID",
            f"仅待处理订单可取消，当前状态: {order.status}",
            {"status": order.status},
        )
    if not faults.enabled("stock_not_restored"):
        _restore_stock(db, order)
    _restore_coupon(db, order)
    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return to_order_out(db, order)


@router.post("/{order_id}/refund", response_model=OrderOut)
def refund_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    order = _order_or_404(db, order_id)
    if user.role != "admin":
        raise AppError(403, "FORBIDDEN", "仅管理员可退款")
    if order.status not in {"paid", "shipped", "completed"}:
        raise AppError(
            409,
            "ORDER_STATE_INVALID",
            f"当前订单状态不可退款: {order.status}",
            {"status": order.status},
        )
    _restore_stock(db, order)
    _restore_coupon(db, order)
    payments = db.scalars(select(Payment).where(Payment.order_id == order.id)).all()
    for payment in payments:
        payment.status = "refunded"
        payment.refunded_at = utcnow()
    order.status = "refunded"
    order.refunded_at = utcnow()
    db.commit()
    db.refresh(order)
    return to_order_out(db, order)


@router.post("/{order_id}/ship", response_model=OrderOut)
def ship_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    order = _order_or_404(db, order_id)
    if user.role != "admin":
        raise AppError(403, "FORBIDDEN", "仅管理员可发货")
    if order.status not in {"created", "paid"}:
        raise AppError(
            409,
            "ORDER_STATE_INVALID",
            f"仅待处理或已支付订单可发货，当前状态: {order.status}",
            {"status": order.status},
        )
    order.status = "shipped"
    db.commit()
    db.refresh(order)
    return to_order_out(db, order)


@router.post("/{order_id}/complete", response_model=OrderOut)
def complete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrderOut:
    order = _order_or_404(db, order_id)
    if user.role != "admin":
        raise AppError(403, "FORBIDDEN", "仅管理员可完成订单")
    if order.status != "shipped":
        raise AppError(
            409,
            "ORDER_STATE_INVALID",
            f"仅已发货订单可完成，当前状态: {order.status}",
            {"status": order.status},
        )
    order.status = "completed"
    db.commit()
    db.refresh(order)
    return to_order_out(db, order)
