from sqlalchemy.orm import Session

from sut.models import Coupon, Order, Product
from sut.schemas import OrderItemOut, OrderOut, ProductOut


def to_product_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        name=product.name,
        description=product.description,
        price_cents=product.price_cents,
        price=round(product.price_cents / 100, 2),
        stock=product.stock,
        category=product.category,
    )


def to_order_out(db: Session, order: Order) -> OrderOut:
    items = []
    for item in order.items:
        product = db.get(Product, item.product_id)
        items.append(
            OrderItemOut(
                product_id=item.product_id,
                product_name=product.name if product else "已删除商品",
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                subtotal_cents=item.unit_price_cents * item.quantity,
            )
        )
    coupon = db.get(Coupon, order.coupon_id) if order.coupon_id else None
    return OrderOut(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        status=order.status,
        subtotal_cents=order.subtotal_cents or order.total_cents,
        discount_cents=order.discount_cents or 0,
        total_cents=order.total_cents,
        coupon_code=coupon.code if coupon else None,
        items=items,
    )
