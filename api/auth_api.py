from api.base import BaseApi


class AuthApi(BaseApi):
    def login(self, username: str, password: str):
        return self.client.post(
            "/auth/login", json_body={"username": username, "password": password}
        )

    def me(self):
        return self.client.get("/auth/me")

    def refresh(self):
        return self.client.post("/auth/refresh")
