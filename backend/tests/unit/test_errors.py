import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.errors import APIError, install_error_handler


def make_test_app() -> FastAPI:
    app = FastAPI()
    install_error_handler(app)

    @app.get("/boom")
    def boom() -> None:
        raise APIError(code="channel_not_found", message="Channel does not exist", status_code=404)

    @app.get("/oops")
    def oops() -> None:
        raise RuntimeError("kaboom")

    return app


@pytest.mark.asyncio
async def test_api_error_is_shaped_envelope() -> None:
    app = make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "channel_not_found", "message": "Channel does not exist"}}


@pytest.mark.asyncio
async def test_uncaught_is_500_internal() -> None:
    app = make_test_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/oops")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal", "message": "Internal Server Error"}}
