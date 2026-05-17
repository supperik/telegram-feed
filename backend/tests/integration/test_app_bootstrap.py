import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_via_async_client(async_client) -> None:
    r = await async_client.get("/internal/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
