from api.base import BaseApi


class OrderApi(BaseApi):
    def create(
        self,
        items: list[dict],
        idempotency_key: str | None = None,
        remark: str = "",
        coupon_code: str | None = None,
    ):
        body = {"items": items, "remark": remark}
        if coupon_code:
            body["coupon_code"] = coupon_code
        return self.client.post(
            "/orders",
            json_body=body,
            idempotency_key=idempotency_key,
        )

    def list(self, page: int | None = None, size: int | None = None, status: str | None = None):
        params = {"page": page, "size": size, "status": status}
        return self.client.get(
            "/orders", params={k: v for k, v in params.items() if v is not None}
        )

    def get(self, order_id: int):
        return self.client.get(f"/orders/{order_id}")

    def cancel(self, order_id: int):
        return self.client.post(f"/orders/{order_id}/cancel")

    def ship(self, order_id: int):
        return self.client.post(f"/orders/{order_id}/ship")

    def complete(self, order_id: int):
        return self.client.post(f"/orders/{order_id}/complete")

    def refund(self, order_id: int):
        return self.client.post(f"/orders/{order_id}/refund")
