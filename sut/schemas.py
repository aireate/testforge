from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    price_cents: int = Field(gt=0, le=10_000_000, description="单价，单位分")
    stock: int = Field(ge=0, le=1_000_000)
    category: str = Field(min_length=1, max_length=50)

    @field_validator("name", "category")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空白字符")
        return value


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    price_cents: int | None = Field(default=None, gt=0, le=10_000_000)
    stock: int | None = Field(default=None, ge=0, le=1_000_000)
    category: str | None = Field(default=None, min_length=1, max_length=50)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price_cents: int
    price: float
    stock: int
    category: str


class StockChange(BaseModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000)


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    size: int
    pages: int


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=999)


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    title: str = Field(min_length=2, max_length=100)
    type: Literal["fixed", "percent"]
    value: int = Field(gt=0, le=10_000_000, description="固定金额（分）或折扣百分比")
    min_spend_cents: int = Field(default=0, ge=0, le=10_000_000)
    total_quantity: int = Field(default=100, ge=1, le=1_000_000)
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @field_validator("code")
    @classmethod
    def _upper_code(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _check_rules(self) -> "CouponCreate":
        if self.type == "percent" and self.value > 100:
            raise ValueError("百分比折扣不能超过 100")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to 必须晚于 valid_from")
        return self


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    type: str
    value: int
    min_spend_cents: int
    total_quantity: int
    claimed_quantity: int
    valid_from: datetime
    valid_to: datetime


class UserCouponOut(BaseModel):
    id: int
    status: str
    order_id: int | None
    coupon: CouponOut


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=20)
    remark: str = Field(default="", max_length=200)
    coupon_code: str | None = Field(default=None, max_length=20)

    @field_validator("coupon_code")
    @classmethod
    def _normalize_coupon(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        return value or None

    @field_validator("items")
    @classmethod
    def _no_duplicate_product(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("同一订单不允许重复商品，请合并数量")
        return items


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price_cents: int
    subtotal_cents: int


class OrderOut(BaseModel):
    id: int
    order_no: str
    user_id: int
    status: str
    subtotal_cents: int
    discount_cents: int
    total_cents: int
    coupon_code: str | None = None
    items: list[OrderItemOut]


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    size: int
    pages: int


class PaymentCallback(BaseModel):
    order_no: str = Field(min_length=4, max_length=40)
    trade_no: str = Field(min_length=4, max_length=64)
    amount_cents: int = Field(gt=0)
    status: Literal["success", "failed"] = "success"
    timestamp: int | None = None


class PaymentCallbackOut(BaseModel):
    received: bool = True
    order_no: str
    order_status: str
    duplicate: bool = False
