import tomllib
from pathlib import Path

from fastapi.testclient import TestClient


def test_api_version_matches_pyproject():
    """api/__init__.py.__version__ is the runtime source of truth (Dockerfile
    installs deps with --no-root, so importlib.metadata fails). It must stay
    in sync with pyproject.toml — if they drift, the health endpoint silently
    lies about which release is running. See 5wm.
    """
    from api import __version__

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["tool"]["poetry"]["version"] == __version__


def test_health_returns_ok(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    from shared.config import get_settings
    get_settings.cache_clear()

    from api.main import app
    with TestClient(app) as client:
        r = client.get("/internal/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        # 0.0.0 is the importlib.metadata.PackageNotFoundError fallback —
        # it fires when Dockerfile installs deps with --no-root and the
        # project package itself isn't installed. health must expose the
        # real version regardless of how deps were laid down. See 5wm.
        assert body["version"] != "0.0.0"
