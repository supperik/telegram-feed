import asyncio
import io
import sys
import uuid

import pytest


def _set_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)


@pytest.mark.integration
def test_create_admin_pure_helper_inserts_and_returns_secret(
    monkeypatch, pg_container, configured_env
):
    # We use a real testcontainers session here because the helper writes to DB.
    email = f"fresh-{uuid.uuid4().hex}@example.com"

    async def run():
        from sqlalchemy import select

        from scripts.create_admin import create_admin
        from shared.db import make_engine, make_session_factory
        from shared.models import Admin

        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            row, secret = await create_admin(
                email,
                "hunter2!",
                display_name="Owner",
                session=s,
            )
            await s.commit()
            assert row.id is not None
            assert row.email == email
            assert row.password_hash.startswith("$argon2")
            assert len(secret) >= 16
            # Verify the row exists.
            r = await s.execute(select(Admin).where(Admin.email == email))
            persisted = r.scalar_one()
            assert persisted.totp_secret == secret
        await engine.dispose()

    asyncio.run(run())


@pytest.mark.integration
def test_create_admin_raises_on_duplicate_email(
    monkeypatch, pg_container, configured_env
):
    email = f"dup-{uuid.uuid4().hex}@example.com"

    async def run():
        from scripts.create_admin import AdminAlreadyExists, create_admin
        from shared.db import make_engine, make_session_factory

        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            await create_admin(email, "pass1", display_name="A", session=s)
            await s.commit()
        async with sf() as s:
            with pytest.raises(AdminAlreadyExists):
                await create_admin(email, "pass2", display_name="B", session=s)
        await engine.dispose()

    asyncio.run(run())


def test_print_qr_writes_ascii_block_to_stdout(monkeypatch):
    """print_qr should render an ASCII QR for an otpauth:// URI to stdout."""
    _set_env(monkeypatch)
    from scripts.create_admin import print_qr

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    print_qr("otpauth://totp/test:foo@bar?secret=JBSWY3DPEHPK3PXP&issuer=test")
    out = buf.getvalue()
    # QR code blocks are made of one or more of these characters:
    #   '█' (full block, U+2588), ' ', '▄', '▀', or '#' depending on library mode.
    # We accept any of them; require at least 4 lines and 10+ visible chars.
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) >= 4
    # Check for at least one common QR-block char.
    assert any(c in out for c in ("█", "▀", "▄", "#"))
