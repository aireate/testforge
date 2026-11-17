"""缺陷注入开关。

通过环境变量 ``TESTFORGE_FAULTS`` 启用，多个缺陷用逗号分隔，例如：

    TESTFORGE_FAULTS=stock_oversell,idempotency_ignore

默认不注入任何缺陷，正常测试行为不变。该机制用于验证测试用例能否真正发现缺陷，
而不是只证明「接口能调通」。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FaultSpec:
    id: str
    area: str
    title: str


FAULT_SPECS: tuple[FaultSpec, ...] = (
    FaultSpec("stock_oversell", "库存", "下单时不校验库存，允许超卖"),
    FaultSpec("stock_not_restored", "库存", "取消订单不归还库存"),
    FaultSpec("stock_negative_allowed", "库存", "库存调整允许减为负数"),
    FaultSpec("idempotency_ignore", "订单", "忽略 Idempotency-Key，重复下单"),
    FaultSpec("total_off_by_one", "订单", "订单总价少算 1 分"),
    FaultSpec("order_state_skip", "订单", "取消订单跳过状态机校验"),
    FaultSpec("authz_missing", "权限", "查询/取消订单跳过归属校验"),
    FaultSpec("admin_check_removed", "权限", "普通用户可执行管理员操作"),
    FaultSpec("token_expiry_ignored", "鉴权", "接受已过期的 Token"),
    FaultSpec("pagination_offset", "商品", "分页偏移多跳一页"),
    FaultSpec("keyword_ignored", "商品", "搜索关键字被忽略"),
    FaultSpec("delete_in_use_allowed", "商品", "允许删除已被订单引用的商品"),
    FaultSpec("coupon_double_use", "优惠券", "同一张优惠券可重复使用"),
    FaultSpec("discount_ignored", "优惠券", "下单时忽略优惠券折扣"),
    FaultSpec("payment_signature_skip", "支付", "支付回调跳过签名校验"),
    FaultSpec("payment_amount_ignore", "支付", "支付回调不校验金额"),
)

_FAULT_IDS = frozenset(spec.id for spec in FAULT_SPECS)


def active_faults() -> frozenset[str]:
    raw = os.getenv("TESTFORGE_FAULTS", "")
    requested = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return frozenset(requested & _FAULT_IDS)


def enabled(fault_id: str) -> bool:
    return fault_id in active_faults()
