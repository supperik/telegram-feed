import pyotp


def test_generate_base32_secret():
    from shared.admin_security.totp import generate_totp_secret
    s = generate_totp_secret()
    assert isinstance(s, str)
    assert len(s) >= 16
    # Base32 alphabet: A-Z and 2-7
    assert set(s) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


def test_verify_current_code_matches():
    from shared.admin_security.totp import generate_totp_secret, verify_totp
    s = generate_totp_secret()
    code = pyotp.TOTP(s).now()
    assert verify_totp(s, code) is True
    assert verify_totp(s, "000000") is False


def test_verify_accepts_adjacent_window_for_clock_skew():
    """valid_window=1 should accept the previous interval as well."""
    from shared.admin_security.totp import verify_totp
    import datetime
    secret = "JBSWY3DPEHPK3PXP"
    totp = pyotp.TOTP(secret)
    # Manually compute the code from one interval ago.
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    past = now - datetime.timedelta(seconds=30)
    past_code = totp.at(past)
    # Today's verify (which uses "now" internally) should still accept the past_code.
    assert verify_totp(secret, past_code) is True


def test_provisioning_uri_format():
    from shared.admin_security.totp import provisioning_uri
    uri = provisioning_uri("JBSWY3DPEHPK3PXP", "alice@example.com", "telegram-feed")
    assert uri.startswith("otpauth://totp/")
    assert "telegram-feed" in uri
    assert "alice@example.com" in uri or "alice%40example.com" in uri
    assert "secret=JBSWY3DPEHPK3PXP" in uri
