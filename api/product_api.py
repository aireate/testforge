from api.base import BaseApi


class ProductApi(BaseApi):
    def list(
        self,
        page: int | None = None,
        size: int | None = None,
        keyword: str | None = None,
        category: str | None = None,
        in_stock: bool | None = None,
        sort: str | None = None,
    ):
        params = {
            "page": page,
            "size": size,
            "keyword": keyword,
            "category": category,
            "in_stock": in_stock,
            "sort": sort,
        }
        return self.client.get(
            "/products", params={k: v for k, v in params.items() if v is not None}
        )

    def get(self, product_id: int | str):
        return self.client.get(f"/products/{product_id}")

    def create(self, payload: dict):
        return self.client.post("/products", json_body=payload)

    def update(self, product_id: int, payload: dict):
        return self.client.put(f"/products/{product_id}", json_body=payload)

    def change_stock(self, product_id: int, delta: int):
        return self.client.patch(
            f"/products/{product_id}/stock", json_body={"delta": delta}
        )

    def delete(self, product_id: int):
        return self.client.delete(f"/products/{product_id}")
