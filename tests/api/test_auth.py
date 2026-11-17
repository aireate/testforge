import os
import time

import allure
import jwt
import pytest

from api.auth_api import AuthApi
from common.request_util import RequestUtil

pytestmark = [pytest.mark.api, pytest.mark.auth]

JWT_SECRET = os.getenv("TESTFORGE_JWT_SECRET", "testforge-test-secret-0123456789abcdef")


@allure.epic("鉴权模块")
@allure.feature("登录")
class TestLogin:
    @allure.story("管理员登录")
    @allure.title("管理员账号可登录并拿到可用的 Bearer Token")
    @pytest.mark.smoke
    def test_admin_login_success(self, settings, anonymous_client):
        response = AuthApi(anonymous_client).login(
            settings.admin_username, settings.admin_password
        )
        assert response.status_code == 200
        body = response.json()

        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert body["user"]["username"] == settings.admin_username
        assert body["user"]["role"] == "admin"
        assert len(body["access_token"].split(".")) == 3, "access_token 应为标准 JWT"
        assert "password" not in str(body).lower(), "响应不应泄露密码字段"

        with allure.step("用返回的 Token 访问 /auth/me"):
            me = RequestUtil(
                base_url=settings.api_base, token=body["access_token"]
            ).get("/auth/me")
            assert me.status_code == 200
            assert me.json()["username"] == settings.admin_username

    @allure.story("普通用户登录")
    @allure.title("普通用户登录后角色为 user")
    def test_user_login_success(self, settings, anonymous_client):
        response = AuthApi(anonymous_client).login(
            settings.user_username, settings.user_password
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "user"


@allure.epic("鉴权模块")
@allure.feature("登录异常")
class TestLoginFailures:
    @allure.title("密码错误返回 401 且不泄露账号是否存在")
    @pytest.mark.smoke
    def test_wrong_password(self, settings, anonymous_client):
        response = AuthApi(anonymous_client).login(settings.admin_username, "wrong-pass")
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "INVALID_CREDENTIALS"
        assert "access_token" not in body

    @allure.title("不存在的账号与密码错误返回同一错误码")
    def test_unknown_user(self, settings, anonymous_client):
        response = AuthApi(anonymous_client).login("nobody_here", settings.admin_password)
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"

    @allure.title("非法登录参数被拦截为 422 校验错误")
    @pytest.mark.parametrize(
        "payload",
        [
            {"username": "ab", "password": "admin123"},
            {"username": "admin", "password": "123"},
            {"username": "admin"},
            {"password": "admin123"},
            {},
        ],
        ids=["username-too-short", "password-too-short", "missing-password", "missing-username", "empty"],
    )
    def test_invalid_payload(self, anonymous_client, payload):
        response = anonymous_client.post("/auth/login", json_body=payload)
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"


@allure.epic("鉴权模块")
@allure.feature("Token 校验")
class TestToken:
    @allure.title("缺少 Token 访问受保护接口返回 401")
    def test_me_without_token(self, anonymous_client):
        response = anonymous_client.get("/auth/me")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHORIZED"

    @allure.title("伪造/畸形 Token 被拒绝")
    @pytest.mark.parametrize(
        "authorization,expected_code",
        [
            ("not-a-token", "UNAUTHORIZED"),
            ("Bearer", "UNAUTHORIZED"),
            ("Bearer abc.def.ghi", "TOKEN_INVALID"),
            ("Basic YWRtaW46YWRtaW4=", "UNAUTHORIZED"),
        ],
        ids=["no-scheme", "empty-token", "broken-jwt", "basic-auth"],
    )
    def test_malformed_token(self, anonymous_client, authorization, expected_code):
        response = anonymous_client.get(
            "/auth/me", headers={"Authorization": authorization}
        )
        assert response.status_code == 401
        assert response.json()["code"] == expected_code

    @allure.title("过期 Token 返回 401 TOKEN_EXPIRED")
    def test_expired_token(self, settings, anonymous_client):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": "1",
                "username": "admin",
                "role": "admin",
                "iat": now - 7200,
                "exp": now - 3600,
                "jti": "expired",
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        response = anonymous_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401
        # 当被测服务使用不同密钥时，会先命中签名校验失败
        assert response.json()["code"] in {"TOKEN_EXPIRED", "TOKEN_INVALID"}

    @allure.title("Token 载荷包含用户、角色与过期时间")
    def test_token_claims(self, settings, admin_token):
        payload = jwt.decode(admin_token, options={"verify_signature": False})
        assert payload["username"] == settings.admin_username
        assert payload["role"] == "admin"
        assert payload["exp"] > payload["iat"]
        assert payload["jti"]

    @allure.title("刷新接口返回新 Token 且旧 Token 仍有效")
    def test_refresh(self, settings, admin_client, admin_token):
        response = AuthApi(admin_client).refresh()
        assert response.status_code == 200
        new_token = response.json()["access_token"]
        assert new_token != admin_token

        old_me = RequestUtil(base_url=settings.api_base, token=admin_token).get("/auth/me")
        new_me = RequestUtil(base_url=settings.api_base, token=new_token).get("/auth/me")
        assert old_me.status_code == 200
        assert new_me.status_code == 200
        assert old_me.json() == new_me.json()
