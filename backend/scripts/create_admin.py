"""Interactive script to create the first sysadmin.

Run via: `bash infra/scripts/create_admin.sh` (which `docker compose exec`s
into the api container and invokes this script).

Pure-core API:
    create_admin(email, password, display_name, *, session) -> (Admin, secret)
    AdminAlreadyExists — raised on duplicate email.
    print_qr(uri) — render an ASCII QR for the provisioning URI to stdout.

Interactive entrypoint: main() — uses input/getpass.
"""
from __future__ import annotations

import asyncio
import sys
from getpass import getpass
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.admin_security.passwords import hash_password
from shared.admin_security.totp import generate_totp_secret, provisioning_uri
from shared.config import get_settings
from shared.db import make_engine, make_session_factory
from shared.models import Admin, AdminAction


class AdminAlreadyExists(Exception):
    pass


async def create_admin(
    email: str,
    password: str,
    *,
    display_name: str | None = None,
    session: AsyncSession,
) -> tuple[Admin, str]:
    """Pure-ish core: hash password, generate TOTP secret, insert Admin row,
    record an AdminAction for the bootstrap.

    Caller commits the session. Caller can also call this from a script's
    main() (interactive flow) or from tests directly.

    Raises:
        AdminAlreadyExists: if an admin row with `email` already exists.
    """
    existing = await session.execute(select(Admin).where(Admin.email == email))
    if existing.scalar_one_or_none() is not None:
        raise AdminAlreadyExists(email)

    secret = generate_totp_secret()
    admin = Admin(
        email=email,
        password_hash=hash_password(password),
        totp_secret=secret,
    )
    session.add(admin)
    try:
        await session.flush()
    except IntegrityError as e:
        # Race: another process inserted the same email between our SELECT
        # and INSERT. Translate to the same domain error.
        raise AdminAlreadyExists(email) from e

    target: dict[str, Any] = {
        "admin_id": admin.id,
        "email": email,
    }
    if display_name:
        target["display_name"] = display_name

    await session.execute(
        insert(AdminAction).values(
            admin_id=admin.id,
            action="admin_created",
            target=target,
        )
    )
    return admin, secret


def print_qr(uri: str) -> None:
    """Render an ASCII QR code for `uri` to stdout using `qrcode`'s
    print_ascii."""
    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    qr.print_ascii(out=sys.stdout, invert=False)


def _prompt_password() -> str:
    """Prompt twice and confirm."""
    while True:
        p1 = getpass("Password: ")
        if not p1:
            print("Password must not be empty.", file=sys.stderr)
            continue
        p2 = getpass("Confirm:  ")
        if p1 != p2:
            print("Passwords do not match. Try again.\n", file=sys.stderr)
            continue
        return p1


async def main() -> int:
    settings = get_settings()
    print(f"Creating admin in DB {settings.postgres_dsn.split('@', 1)[-1]}\n")

    email = input("Admin email: ").strip()
    if not email:
        print("Email is required.", file=sys.stderr)
        return 1
    password = _prompt_password()
    display_name = input("Display name (optional): ").strip() or None

    engine = make_engine(settings.postgres_dsn)
    sf = make_session_factory(engine)
    try:
        async with sf() as session:
            try:
                admin, secret = await create_admin(
                    email, password,
                    display_name=display_name,
                    session=session,
                )
                await session.commit()
            except AdminAlreadyExists:
                print(
                    f"\nAn admin with email '{email}' already exists. Aborting.",
                    file=sys.stderr,
                )
                return 1

        uri = provisioning_uri(secret, email, "telegram-feed")
        print("\nAdmin created.")
        print(f"  id:     {admin.id}")
        print(f"  email:  {admin.email}")
        print(f"  secret: {secret}")
        print(f"  uri:    {uri}")
        print("\nScan this QR with your Authenticator app NOW (it won't be shown again):\n")
        print_qr(uri)
        print("\nYou can also enter the secret manually if you can't scan.")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
