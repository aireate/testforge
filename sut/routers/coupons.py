from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sut.database import get_db
from sut.deps import get_current_user, require_admin
from sut.errors import AppError
from sut.models import Coupon, User, UserCoupon, utcnow_naive
from sut.schemas import CouponCreate, CouponOut, UserCouponOut

router = APIRouter(prefix="/coupons", tags=["coupons"])


def _coupon_or_404(db: Session, code: str) -> Coupon:
    coupon = db.scalar(select(Coupon).where(Coupon.code == code.upper()))
    if coupon is None:
        raise AppError(404, "COUPON_NOT_FOUND", f"优惠券 {code} 不存在")
    return coupon


@router.post("", response_model=CouponOut, status_code=201)
def create_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> CouponOut:
    if db.scalar(select(Coupon).where(Coupon.code == payload.code)) is not None:
        raise AppError(409, "COUPON_CODE_EXISTS", f"优惠券编码 {payload.code} 已存在")

    valid_from = payload.valid_from or utcnow_naive()
    valid_to = payload.valid_to or valid_from + timedelta(days=30)
    coupon = Coupon(
        code=payload.code,
        title=payload.title,
        type=payload.type,
        value=payload.value,
        min_spend_cents=payload.min_spend_cents,
        total_quantity=payload.total_quantity,
        claimed_quantity=0,
        valid_from=valid_from.replace(tzinfo=None),
        valid_to=valid_to.replace(tzinfo=None),
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return CouponOut.model_validate(coupon)


@router.get("", response_model=list[CouponOut])
def list_coupons(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CouponOut]:
    now = utcnow_naive()
    coupons = db.scalars(
        select(Coupon)
        .where(Coupon.valid_from <= now, Coupon.valid_to >= now)
        .order_by(Coupon.id.desc())
    ).all()
    return [CouponOut.model_validate(coupon) for coupon in coupons]


@router.get("/mine", response_model=list[UserCouponOut])
def my_coupons(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[UserCouponOut]:
    owned = db.scalars(
        select(UserCoupon)
        .where(UserCoupon.user_id == user.id)
        .order_by(UserCoupon.id.desc())
    ).all()
    return [
        UserCouponOut(
            id=item.id,
            status=item.status,
            order_id=item.order_id,
            coupon=CouponOut.model_validate(item.coupon),
        )
        for item in owned
    ]


@router.post("/{code}/claim", response_model=UserCouponOut)
def claim_coupon(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserCouponOut:
    coupon = _coupon_or_404(db, code)
    now = utcnow_naive()
    if now < coupon.valid_from or now > coupon.valid_to:
        raise AppError(409, "COUPON_EXPIRED", "优惠券不在有效期内")

    existing = db.scalar(
        select(UserCoupon).where(
            UserCoupon.user_id == user.id, UserCoupon.coupon_id == coupon.id
        )
    )
    if existing is not None:
        raise AppError(409, "COUPON_ALREADY_CLAIMED", "每人限领一张")

    # 条件更新保证并发领取不会超发
    result = db.execute(
        update(Coupon)
        .where(Coupon.id == coupon.id, Coupon.claimed_quantity < Coupon.total_quantity)
        .values(claimed_quantity=Coupon.claimed_quantity + 1)
    )
    if result.rowcount == 0:
        db.rollback()
        raise AppError(409, "COUPON_SOLD_OUT", "优惠券已领完")

    user_coupon = UserCoupon(user_id=user.id, coupon_id=coupon.id, status="unused")
    db.add(user_coupon)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "COUPON_ALREADY_CLAIMED", "每人限领一张") from exc
    db.refresh(user_coupon)
    return UserCouponOut(
        id=user_coupon.id,
        status=user_coupon.status,
        order_id=user_coupon.order_id,
        coupon=CouponOut.model_validate(user_coupon.coupon),
    )
