import asyncio
import uuid

import pyotp
import pytest
from fastapi.testclient import TestClient


def _seed_admin_with_actions(pg_container, *, n_actions: int = 3):
    """Insert an admin and N AdminAction rows belonging to that admin."""
    from sqlalchemy import insert
    from shared.admin_security.passwords import hash_password
    from shared.admin_security.totp import generate_totp_secret
    from shared.db import make_engine, make_session_factory
    from shared.models import Admin, AdminAction

    secret = generate_totp_secret()
    email = f"acts-{uuid.uuid4().hex[:8]}@example.com"

    async def run():
        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            row = Admin(email=email, password_hash=hash_password("hunter2!"), totp_secret=secret)
            s.add(row)
            await s.commit()
            await s.refresh(row)
            for i in range(n_actions):
                act = "ban_channel" if i % 2 == 0 else "unban_channel"
                await s.execute(insert(AdminAction).values(
                    admin_id=row.id,
                    action=act,
                    target={"channel_id": 1000 + i, "i": i},
                ))
            await s.commit()
        await engine.dispose()
        return {"id": row.id, "email": email, "password": "hunter2!", "secret": secret,
                "n": n_actions}

    return asyncio.run(run())


def _login(client, admin):
    code = pyotp.TOTP(admin["secret"]).now()
    r = client.post("/admin/login", json={
        "email": admin["email"], "password": admin["password"], "totp": code,
    })
    return r.json()["access_token"]


@pytest.fixture
def acts_admin(configured_env, pg_container):
    return _seed_admin_with_actions(pg_container, n_actions=5)


@pytest.mark.integration
def test_admin_actions_requires_admin_auth(configured_env, acts_admin):
    from api.main import app
    with TestClient(app) as client:
        r = client.get("/admin/admin-actions")
        assert r.status_code == 401


@pytest.mark.integration
def test_admin_actions_lists_reverse_chronological(configured_env, acts_admin):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, acts_admin)
        r = client.get("/admin/admin-actions",
                       headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "actions" in body
        assert len(body["actions"]) >= 5
        # IDs descending.
        ids = [a["id"] for a in body["actions"]]
        assert ids == sorted(ids, reverse=True)
        # Each row has admin_email.
        seeded_ids = {a["id"] for a in body["actions"]
                      if a["admin_id"] == acts_admin["id"]}
        assert len(seeded_ids) >= 5
        assert any(a["admin_email"] == acts_admin["email"] for a in body["actions"])


@pytest.mark.integration
def test_admin_actions_filter_by_action(configured_env, acts_admin):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, acts_admin)
        r = client.get(
            "/admin/admin-actions?action=ban_channel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        for a in body["actions"]:
            assert a["action"] == "ban_channel"


@pytest.mark.integration
def test_admin_actions_filter_by_admin_id(configured_env, acts_admin):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, acts_admin)
        r = client.get(
            f"/admin/admin-actions?admin_id={acts_admin['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["actions"]) >= 5
        for a in body["actions"]:
            assert a["admin_id"] == acts_admin["id"]


@pytest.mark.integration
def test_admin_actions_cursor_pagination(configured_env, acts_admin):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, acts_admin)
        page1 = client.get(
            f"/admin/admin-actions?admin_id={acts_admin['id']}&limit=2",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        assert len(page1["actions"]) == 2
        assert page1["next_cursor"] is not None
        page2 = client.get(
            f"/admin/admin-actions?admin_id={acts_admin['id']}&limit=2&cursor={page1['next_cursor']}",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        assert len(page2["actions"]) <= 2
        # Page 2's first id is strictly less than page 1's last id.
        if page2["actions"]:
            assert page2["actions"][0]["id"] < page1["actions"][-1]["id"]
