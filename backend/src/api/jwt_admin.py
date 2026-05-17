import datetime as dt

import jwt

from shared.config import get_settings


ADMIN_JWT_ISSUER = "telegram-feed-admin"


def _admin_key() -> str:
    """Namespace the JWT secret so admin tokens are cryptographically separate
    from user tokens even when API_JWT_SECRET is shared."""
    return get_settings().api_jwt_secret + ":admin"


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def issue_admin_access(admin_id: int) -> str:
    s = get_settings()
    now = _now()
    payload = {
        "iss": ADMIN_JWT_ISSUER,
        "sub": str(admin_id),
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=s.api_jwt_access_ttl_seconds)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _admin_key(), algorithm=s.api_jwt_algorithm)


def issue_admin_refresh(admin_id: int) -> str:
    s = get_settings()
    now = _now()
    payload = {
        "iss": ADMIN_JWT_ISSUER,
        "sub": str(admin_id),
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=s.api_jwt_refresh_ttl_seconds)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, _admin_key(), algorithm=s.api_jwt_algorithm)


def decode_admin_token(token: str, *, expected_type: str = "access") -> dict:
    s = get_settings()
    payload = jwt.decode(
        token,
        _admin_key(),
        algorithms=[s.api_jwt_algorithm],
        issuer=ADMIN_JWT_ISSUER,
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected type={expected_type}, got {payload.get('type')}")
    return payload
