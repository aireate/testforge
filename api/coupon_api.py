from api.base import BaseApi


class CouponApi(BaseApi):
    def create(
        self,
        code: str,
        type: str = "fixed",
        value: int = 1000,
        min_spend_cents: int = 0,
        total_quantity: int = 100,
        title: str = "测试优惠券",
        valid_from: str | None = None,
        valid_to: str | None = None,
    ):
        body = {
            "code": code,
            "title": title,
            "type": type,
            "value": value,
            "min_spend_cents": min_spend_cents,
            "total_quantity": total_quantity,
        }
        if valid_from:
            body["valid_from"] = valid_from
        if valid_to:
            body["valid_to"] = valid_to
        return self.client.post("/coupons", json_body=body)

    def list(self):
        return self.client.get("/coupons")

    def mine(self):
        return self.client.get("/coupons/mine")

    def claim(self, code: str):
        return self.client.post(f"/coupons/{code}/claim")
