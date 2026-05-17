def test_session_dir_default(monkeypatch):
    monkeypatch.delenv("TG_SESSIONS_DIR", raising=False)
    from ingester.session import default_sessions_dir
    assert default_sessions_dir() == "/app/sessions"


def test_session_dir_env_override(monkeypatch):
    monkeypatch.setenv("TG_SESSIONS_DIR", "/tmp/x")
    from ingester.session import default_sessions_dir
    assert default_sessions_dir() == "/tmp/x"
