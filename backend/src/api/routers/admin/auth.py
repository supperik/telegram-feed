from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.jwt_admin import (
    decode_admin_token,
    issue_admin_access,
    issue_admin_refresh,
)
from shared.admin_security.passwords import verify_password
from shared.admin_security.totp import verify_totp
from shared.models import Admin


router = APIRouter(prefix="/admin", tags=["admin"])


class LoginRequest(BaseModel):
    email: str
    password: str
    totp: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def _bad(code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code}},
    )


@router.post("/login", response_model=TokenPair)
async def admin_login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    res = await session.execute(select(Admin).where(Admin.email == body.email))
    admin = res.scalar_one_or_none()
    if admin is None or not verify_password(admin.password_hash, body.password):
        raise _bad("invalid_credentials")
    if admin.totp_secret and not verify_totp(admin.totp_secret, body.totp):
        raise _bad("invalid_totp")
    return TokenPair(
        access_token=issue_admin_access(admin.id),
        refresh_token=issue_admin_refresh(admin.id),
    )


@router.post("/refresh", response_model=TokenPair)
async def admin_refresh(body: RefreshRequest) -> TokenPair:
    try:
        payload = decode_admin_token(body.refresh_token, expected_type="refresh")
    except Exception:
        raise _bad("invalid_refresh")
    admin_id = int(payload["sub"])
    return TokenPair(
        access_token=issue_admin_access(admin_id),
        refresh_token=issue_admin_refresh(admin_id),
    )
