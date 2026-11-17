from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=20)
    remark: str = Field(default="", max_length=200)

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
    total_cents: int
    items: list[OrderItemOut]


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    size: int
    pages: int
