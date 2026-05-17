import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient


def _seed_admin(pg_container, *, email=None, password="hunter2!", totp_secret=None):
    """Insert one admin directly via async session. Returns the inserted row.

    Email is randomized per call so multiple tests against the session-scoped
    Postgres container don't collide on the unique-email constraint.
    """
    from shared.admin_security.passwords import hash_password
    from shared.admin_security.totp import generate_totp_secret
    from shared.db import make_engine, make_session_factory
    from shared.models import Admin

    secret = totp_secret or generate_totp_secret()
    addr = email or f"admin-{uuid.uuid4().hex}@example.com"

    async def run():
        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            row = Admin(
                email=addr,
                password_hash=hash_password(password),
                totp_secret=secret,
            )
            s.add(row)
            await s.commit()
            await s.refresh(row)
            await engine.dispose()
            return {"id": row.id, "email": row.email, "secret": secret}

    return asyncio.run(run())


@pytest.fixture
def admin_record(configured_env, pg_container):
    return _seed_admin(pg_container)


@pytest.mark.integration
def test_admin_login_happy_path(configured_env, admin_record):
    import pyotp
    from api.main import app

    code = pyotp.TOTP(admin_record["secret"]).now()
    with TestClient(app) as client:
        r = client.post("/admin/login", json={
            "email": admin_record["email"],
            "password": "hunter2!",
            "totp": code,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"


@pytest.mark.integration
def test_admin_login_wrong_password(configured_env, admin_record):
    import pyotp
    from api.main import app

    code = pyotp.TOTP(admin_record["secret"]).now()
    with TestClient(app) as client:
        r = client.post("/admin/login", json={
            "email": admin_record["email"],
            "password": "WRONG",
            "totp": code,
        })
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "invalid_credentials"


@pytest.mark.integration
def test_admin_login_wrong_totp(configured_env, admin_record):
    from api.main import app
    with TestClient(app) as client:
        r = client.post("/admin/login", json={
            "email": admin_record["email"],
            "password": "hunter2!",
            "totp": "000000",
        })
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "invalid_totp"


@pytest.mark.integration
def test_admin_login_unknown_email(configured_env, admin_record):
    import pyotp
    from api.main import app
    code = pyotp.TOTP(admin_record["secret"]).now()
    with TestClient(app) as client:
        r = client.post("/admin/login", json={
            "email": "ghost@example.com",
            "password": "hunter2!",
            "totp": code,
        })
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "invalid_credentials"


@pytest.mark.integration
def test_admin_refresh_happy_path(configured_env, admin_record):
    import pyotp
    from api.main import app

    code = pyotp.TOTP(admin_record["secret"]).now()
    with TestClient(app) as client:
        login = client.post("/admin/login", json={
            "email": admin_record["email"],
            "password": "hunter2!",
            "totp": code,
        }).json()
        refresh = login["refresh_token"]

        r = client.post("/admin/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]


@pytest.mark.integration
def test_admin_refresh_rejects_access_token(configured_env, admin_record):
    """Passing an access token to /admin/refresh should fail (wrong type claim)."""
    import pyotp
    from api.main import app

    code = pyotp.TOTP(admin_record["secret"]).now()
    with TestClient(app) as client:
        login = client.post("/admin/login", json={
            "email": admin_record["email"],
            "password": "hunter2!",
            "totp": code,
        }).json()
        access = login["access_token"]
        r = client.post("/admin/refresh", json={"refresh_token": access})
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "invalid_refresh"
