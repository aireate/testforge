import math

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from sut import faults
from sut.database import get_db
from sut.deps import get_current_user, require_admin
from sut.errors import AppError
from sut.models import OrderItem, Product, User
from sut.schemas import (
    ProductCreate,
    ProductOut,
    ProductPage,
    ProductUpdate,
    StockChange,
)
from sut.utils import to_product_out

router = APIRouter(prefix="/products", tags=["products"])

SORT_FIELDS = {
    "price_asc": Product.price_cents.asc(),
    "price_desc": Product.price_cents.desc(),
    "name": Product.name.asc(),
    "newest": Product.id.desc(),
}


def _get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", f"商品 {product_id} 不存在")
    return product


@router.get("", response_model=ProductPage)
def list_products(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=50),
    keyword: str | None = Query(default=None, max_length=50),
    category: str | None = Query(default=None, max_length=50),
    in_stock: bool | None = Query(default=None),
    sort: str = Query(default="newest"),
    db: Session = Depends(get_db),
) -> ProductPage:
    if sort not in SORT_FIELDS:
        raise AppError(422, "INVALID_SORT", f"不支持的排序字段: {sort}")

    stmt = select(Product)
    if keyword and not faults.enabled("keyword_ignored"):
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Product.name.like(like), Product.description.like(like)))
    if category:
        stmt = stmt.where(Product.category == category)
    if in_stock is not None:
        stmt = stmt.where(Product.stock > 0) if in_stock else stmt.where(Product.stock == 0)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(SORT_FIELDS[sort])
        .offset(page * size if faults.enabled("pagination_offset") else (page - 1) * size)
        .limit(size)
    ).all()
    return ProductPage(
        items=[to_product_out(p) for p in items],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductOut:
    return to_product_out(_get_product_or_404(db, product_id))


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ProductOut:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return to_product_out(product)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ProductOut:
    product = _get_product_or_404(db, product_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return to_product_out(product)


@router.patch("/{product_id}/stock", response_model=ProductOut)
def change_stock(
    product_id: int,
    payload: StockChange,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ProductOut:
    product = _get_product_or_404(db, product_id)
    statement = update(Product).where(Product.id == product_id)
    if not faults.enabled("stock_negative_allowed"):
        statement = statement.where(Product.stock + payload.delta >= 0)
    result = db.execute(statement.values(stock=Product.stock + payload.delta))
    if result.rowcount == 0:
        db.rollback()
        raise AppError(
            409,
            "STOCK_NEGATIVE",
            "库存不足，无法完成扣减",
            {"product_id": product_id, "current_stock": product.stock, "delta": payload.delta},
        )
    db.commit()
    db.refresh(product)
    return to_product_out(product)


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    product = _get_product_or_404(db, product_id)
    referenced = db.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.product_id == product_id)
    )
    if referenced and not faults.enabled("delete_in_use_allowed"):
        raise AppError(
            409,
            "PRODUCT_IN_USE",
            "商品已被订单引用，不能删除",
            {"order_item_count": referenced},
        )
    db.delete(product)
    db.commit()
    return Response(status_code=204)
