import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import text

from sut import __version__
from sut.database import engine, init_db
from sut.errors import register_error_handlers
from sut.routers import auth, orders, products
from sut.seed import seed_if_empty

STATIC_DIR = Path(__file__).resolve().parent / "static"
API_PREFIX = os.getenv("TESTFORGE_API_PREFIX", "/api/v1")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if os.getenv("TESTFORGE_SEED", "1") == "1":
        seed_if_empty()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TestForge SUT",
        version=__version__,
        description="TestForge 内置被测系统：商品 / 库存 / 订单",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(products.router, prefix=API_PREFIX)
    app.include_router(orders.router, prefix=API_PREFIX)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok", "version": __version__}

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/ui/login")

    @app.get("/ui/login", include_in_schema=False)
    @app.get("/ui/products", include_in_schema=False)
    def ui(_: Request) -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
