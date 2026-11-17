import os
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
import requests

from api.auth_api import AuthApi
from api.order_api import OrderApi
from common.db_util import DbUtil
from common.request_util import RequestUtil
from config.settings import PROJECT_ROOT, Settings

DEFAULT_JWT_SECRET = "testforge-test-secret-0123456789abcdef"


@dataclass(frozen=True)
class SutServer:
    base_url: str
    db_path: Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_healthy(base_url: str, proc: subprocess.Popen, log_path: Path) -> None:
    deadline = time.time() + 40
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
            raise RuntimeError(f"被测服务启动失败（退出码 {proc.returncode}）:\n{tail}")
        try:
            response = requests.get(f"{base_url}/healthz", timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.3)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    raise RuntimeError(f"被测服务 40s 内未就绪:\n{tail}")


@pytest.fixture(scope="session")
def sut_server(tmp_path_factory: pytest.TempPathFactory) -> SutServer:
    """启动一个独占的 SUT 实例（独立端口 + 独立 SQLite 文件）。

    xdist 下每个 worker 都会拿到自己的实例，因此用例可并行、互不污染。
    """
    external = os.getenv("TESTFORGE_EXTERNAL_SUT") == "1"
    external_url = os.getenv("TESTFORGE_BASE_URL", "").rstrip("/")
    if external:
        db_path = Path(os.environ["TESTFORGE_DB"])
        return SutServer(base_url=external_url, db_path=db_path)

    workdir = tmp_path_factory.mktemp("sut")
    db_path = workdir / "testforge.db"
    log_path = workdir / "sut.log"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env.update(
        {
            "TESTFORGE_DB": str(db_path),
            "TESTFORGE_SEED": "1",
            "TESTFORGE_JWT_SECRET": DEFAULT_JWT_SECRET,
            "PYTHONPATH": str(PROJECT_ROOT),
            "PYTHONIOENCODING": "utf-8",
        }
    )

    log_file = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "sut.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_until_healthy(base_url, proc, log_path)
    except RuntimeError:
        proc.kill()
        log_file.close()
        raise

    yield SutServer(base_url=base_url, db_path=db_path)

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    log_file.close()


@pytest.fixture(scope="session")
def settings(sut_server: SutServer) -> Settings:
    base = Settings.from_env()
    timeout = float(os.getenv("TESTFORGE_TIMEOUT", base.timeout))
    retries = int(os.getenv("TESTFORGE_RETRIES", base.retries))
    return replace(
        base,
        base_url=sut_server.base_url,
        timeout=timeout,
        retries=retries,
        db_path=sut_server.db_path,
    )


def _login(settings: Settings, username: str, password: str) -> str:
    client = RequestUtil(base_url=settings.api_base, timeout=settings.timeout)
    response = AuthApi(client).login(username, password)
    assert response.status_code == 200, f"登录失败: {response.status_code} {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token(settings: Settings) -> str:
    return _login(settings, settings.admin_username, settings.admin_password)


@pytest.fixture(scope="session")
def user_token(settings: Settings) -> str:
    return _login(settings, settings.user_username, settings.user_password)


@pytest.fixture(scope="session")
def admin_client(settings: Settings, admin_token: str) -> RequestUtil:
    return RequestUtil(
        base_url=settings.api_base,
        timeout=settings.timeout,
        retries=settings.retries,
        token=admin_token,
    )


@pytest.fixture(scope="session")
def user_client(settings: Settings, user_token: str) -> RequestUtil:
    return RequestUtil(
        base_url=settings.api_base,
        timeout=settings.timeout,
        retries=settings.retries,
        token=user_token,
    )


@pytest.fixture(scope="session")
def anonymous_client(settings: Settings) -> RequestUtil:
    return RequestUtil(
        base_url=settings.api_base, timeout=settings.timeout, retries=settings.retries
    )


@pytest.fixture(scope="session")
def db(sut_server: SutServer) -> DbUtil:
    return DbUtil(sut_server.db_path)


@pytest.fixture
def product_factory(admin_client: RequestUtil):
    """创建商品并在用例结束后删除，保证用例之间数据独立。"""
    from api.product_api import ProductApi

    product_api = ProductApi(admin_client)
    created: list[int] = []

    def _create(**overrides) -> dict:
        payload = {
            "name": f"测试商品-{uuid.uuid4().hex[:8]}",
            "description": "由 product_factory 创建",
            "price_cents": 19900,
            "stock": 20,
            "category": "测试",
        }
        payload.update(overrides)
        response = product_api.create(payload)
        assert response.status_code == 201, f"创建商品失败: {response.status_code} {response.text}"
        product = response.json()
        created.append(product["id"])
        return product

    yield _create

    for product_id in created:
        product_api.delete(product_id)


@pytest.fixture
def order_factory(user_client: RequestUtil):
    """创建订单并在用例结束后取消（取消会归还库存）。"""
    order_api = OrderApi(user_client)
    created: list[dict] = []

    def _create(items: list[dict] | None = None, client: RequestUtil | None = None) -> dict:
        api = OrderApi(client) if client is not None else order_api
        response = api.create(items or [{"product_id": 1, "quantity": 1}])
        assert response.status_code == 201, f"创建订单失败: {response.status_code} {response.text}"
        order = response.json()
        created.append({"api": api, "order": order})
        return order

    yield _create

    for entry in created:
        order, api = entry["order"], entry["api"]
        if order["status"] == "created":
            api.cancel(order["id"])


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """失败时把归因结果附到 Allure，便于直接看到分类与排查动作。"""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    from ai.failure_triage import Failure, classify_failure, render_markdown

    message = str(call.excinfo.value) if call.excinfo is not None else ""
    failure = Failure(
        nodeid=report.nodeid,
        test_name=item.name,
        message=message,
        detail=report.longreprtext,
        duration=report.duration,
    )
    result = classify_failure(failure)
    try:
        import allure

        allure.attach(
            render_markdown([result]),
            name="失败归因",
            attachment_type=allure.attachment_type.TEXT,
        )
    except Exception:  # pragma: no cover - Allure 不可用时不影响用例
        pass
