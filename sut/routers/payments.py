import hmac
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.settings import settings
from sut import faults
from sut.database import get_db
from sut.errors import AppError
from sut.models import Order, Payment, utcnow
from sut.schemas import PaymentCallback, PaymentCallbackOut

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/callback", response_model=PaymentCallbackOut)
async def payment_callback(
    request: Request,
    x_pay_signature: str | None = Header(default=None, alias="X-Pay-Signature"),
    db: Session = Depends(get_db),
) -> PaymentCallbackOut:
    raw = await request.body()

    if not faults.enabled("payment_signature_skip"):
        expected = hmac.new(
            settings.pay_secret.encode(), raw, sha256
        ).hexdigest()
        if not x_pay_signature or not hmac.compare_digest(expected, x_pay_signature):
            raise AppError(401, "INVALID_SIGNATURE", "支付回调签名校验失败")

    try:
        payload = PaymentCallback.model_validate_json(raw)
    except ValidationError as exc:
        raise AppError(422, "INVALID_PAYLOAD", f"回调参数不合法: {exc.errors()}") from exc

    order = db.scalar(select(Order).where(Order.order_no == payload.order_no))
    if order is None:
        raise AppError(404, "ORDER_NOT_FOUND", f"订单 {payload.order_no} 不存在")

    if payload.status == "failed":
        return PaymentCallbackOut(
            order_no=order.order_no, order_status=order.status
        )

    existing = db.scalar(select(Payment).where(Payment.trade_no == payload.trade_no))
    if existing is not None:
        if existing.order_id != order.id or existing.amount_cents != payload.amount_cents:
            raise AppError(409, "PAYMENT_CONFLICT", "交易号已被其他订单或金额使用")
        return PaymentCallbackOut(
            order_no=order.order_no, order_status=order.status, duplicate=True
        )

    if not faults.enabled("payment_amount_ignore") and payload.amount_cents != order.total_cents:
        raise AppError(
            400,
            "PAYMENT_AMOUNT_MISMATCH",
            "回调金额与订单应付金额不一致",
            {"expected": order.total_cents, "actual": payload.amount_cents},
        )

    if order.status != "created":
        raise AppError(
            409,
            "ORDER_STATE_INVALID",
            f"当前订单状态不可支付: {order.status}",
            {"status": order.status},
        )

    payment = Payment(
        order_id=order.id,
        trade_no=payload.trade_no,
        amount_cents=payload.amount_cents,
        status="success",
        raw_body=raw.decode("utf-8", errors="replace"),
    )
    db.add(payment)
    order.status = "paid"
    order.paid_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        # 并发重复回调：唯一约束兜底，按幂等返回
        db.rollback()
        existing = db.scalar(select(Payment).where(Payment.trade_no == payload.trade_no))
        if existing is None:
            raise
        return PaymentCallbackOut(
            order_no=order.order_no, order_status="paid", duplicate=True
        )

    db.refresh(order)
    return PaymentCallbackOut(order_no=order.order_no, order_status=order.status)
