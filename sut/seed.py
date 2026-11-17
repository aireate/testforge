"""初始化种子数据：两个账号 + 10 个商品。"""

from sqlalchemy import select

from sut.database import SessionLocal
from sut.models import Product, User
from sut.security import hash_password

USERS = [
    {"username": "admin", "password": "admin123", "role": "admin"},
    {"username": "user", "password": "user123", "role": "user"},
]

PRODUCTS = [
    ("机械键盘 K870", "87 键热插拔，RGB 背光", 39900, 50, "数码"),
    ("无线鼠标 M330", "静音办公，续航 18 个月", 12900, 120, "数码"),
    ("27 寸显示器 P27", "2K 100Hz，IPS 面板", 129900, 20, "数码"),
    ("USB-C 扩展坞 8 合 1", "HDMI + 千兆网口 + PD 充电", 25900, 60, "配件"),
    ("降噪耳机 Air Pro", "主动降噪，40 小时续航", 89900, 30, "数码"),
    ("人体工学椅 E3", "四向调节腰托，网布透气", 159900, 15, "办公"),
    ("升降桌 1.4m", "双电机，记忆高度", 189900, 8, "办公"),
    ("笔记本支架铝合金", "六档调节，散热镂空", 8900, 200, "配件"),
    ("氮化镓充电器 65W", "双 C 口，支持 PD3.0", 15900, 150, "配件"),
    ("4K 摄像头 Meet", "自动对焦，双麦克风降噪", 69900, 0, "数码"),
]


def seed_if_empty() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        for item in USERS:
            db.add(
                User(
                    username=item["username"],
                    password_hash=hash_password(item["password"]),
                    role=item["role"],
                )
            )
        for name, description, price_cents, stock, category in PRODUCTS:
            db.add(
                Product(
                    name=name,
                    description=description,
                    price_cents=price_cents,
                    stock=stock,
                    category=category,
                )
            )
        db.commit()
