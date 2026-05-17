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


def test_issue_and_decode_admin_access(monkeypatch):
    _set_env(monkeypatch)
    from shared.config import get_settings
    get_settings.cache_clear()
    from api.jwt_admin import issue_admin_access, decode_admin_token, ADMIN_JWT_ISSUER

    tok = issue_admin_access(42)
    payload = decode_admin_token(tok, expected_type="access")
    assert int(payload["sub"]) == 42
    assert payload["iss"] == ADMIN_JWT_ISSUER
    assert payload["type"] == "access"


def test_issue_and_decode_admin_refresh(monkeypatch):
    _set_env(monkeypatch)
    from shared.config import get_settings
    get_settings.cache_clear()
    from api.jwt_admin import issue_admin_refresh, decode_admin_token

    tok = issue_admin_refresh(7)
    payload = decode_admin_token(tok, expected_type="refresh")
    assert int(payload["sub"]) == 7
    assert payload["type"] == "refresh"


def test_decode_rejects_wrong_type(monkeypatch):
    _set_env(monkeypatch)
    from shared.config import get_settings
    get_settings.cache_clear()
    import jwt as pyjwt
    from api.jwt_admin import issue_admin_access, decode_admin_token

    tok = issue_admin_access(1)
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_admin_token(tok, expected_type="refresh")


def test_admin_token_uses_separate_secret(monkeypatch):
    """An admin token signed with secret+':admin' must NOT verify against the
    plain user secret. Validate by manually decoding with the wrong key."""
    _set_env(monkeypatch)
    from shared.config import get_settings
    get_settings.cache_clear()
    s = get_settings()

    import jwt as pyjwt
    from api.jwt_admin import issue_admin_access

    tok = issue_admin_access(99)
    # Decoding with the plain user secret should fail signature verification.
    with pytest.raises(pyjwt.InvalidSignatureError):
        pyjwt.decode(tok, s.api_jwt_secret, algorithms=[s.api_jwt_algorithm], issuer="telegram-feed-admin")
