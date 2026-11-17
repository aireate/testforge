from sqlalchemy.orm import Session

from sut.models import Order, Product
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
    return OrderOut(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        status=order.status,
        total_cents=order.total_cents,
        items=items,
    )
