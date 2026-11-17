import json as jsonlib
import time
from typing import Any

import requests

from common.log_util import error, info

IDEMPOTENT_METHODS = {"GET", "HEAD", "PUT", "PATCH", "DELETE"}


class RequestUtil:
    """统一的 HTTP 客户端封装。

    职责：
    - 复用 Session（连接池 / 默认头）
    - 自动拼接 base_url 与注入 Bearer Token
    - 连接异常与幂等请求 5xx 的重试（指数退避，不做无脑重试）
    - 请求耗时日志与失败响应附件（便于 Allure 定位）
    """

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        retries: int = 2,
        token: str | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.token = token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "TestForge/1.0 (+https://github.com/aireate/testforge)",
            }
        )
        if default_headers:
            self.session.headers.update(default_headers)

    def clone(self, token: str | None = None) -> "RequestUtil":
        return RequestUtil(
            base_url=self.base_url,
            timeout=self.timeout,
            retries=self.retries,
            token=token if token is not None else self.token,
        )

    def set_token(self, token: str | None) -> None:
        self.token = token

    def _build_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        if not self.base_url:
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, extra: dict[str, str] | None, idempotency_key: str | None) -> dict[str, str]:
        headers = dict(extra or {})
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        json: Any = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
        retries: int | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        url = self._build_url(path)
        max_retries = self.retries if retries is None else retries
        last_exc: Exception | None = None

        for attempt in range(max_retries + 1):
            started = time.perf_counter()
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_body if json_body is not None else json,
                    data=data,
                    headers=self._headers(headers, idempotency_key),
                    timeout=self.timeout,
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                # 非幂等请求一旦发出就可能已被服务端处理，重试会造成重复下单
                if method.upper() not in IDEMPOTENT_METHODS or attempt >= max_retries:
                    error(f"{method.upper()} {url} 请求失败（未重试或重试耗尽）: {exc}")
                    raise
                time.sleep(0.2 * (attempt + 1))
                continue

            elapsed_ms = (time.perf_counter() - started) * 1000
            info(f"{method.upper()} {url} -> {response.status_code} ({elapsed_ms:.0f}ms)")

            if (
                method.upper() in IDEMPOTENT_METHODS
                and response.status_code >= 500
                and attempt < max_retries
            ):
                time.sleep(0.2 * (attempt + 1))
                continue

            self._attach_on_failure(method, url, response)
            return response

        raise last_exc  # pragma: no cover - 仅在重试耗尽时触发

    @staticmethod
    def _attach_on_failure(method: str, url: str, response: requests.Response) -> None:
        if response.status_code < 400:
            return
        try:
            import allure

            allure.attach(
                f"{method.upper()} {url}\n\n"
                f"status: {response.status_code}\n\n"
                f"headers: {jsonlib.dumps(dict(response.headers), ensure_ascii=False, indent=2)}\n\n"
                f"body: {response.text[:4000]}",
                name="HTTP 失败响应",
                attachment_type=allure.attachment_type.TEXT,
            )
        except Exception:  # pragma: no cover - Allure 缺失时不影响用例执行
            pass

    # 便捷方法
    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self.request("DELETE", path, **kwargs)
