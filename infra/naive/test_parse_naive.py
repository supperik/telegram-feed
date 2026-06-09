"""Tests for parse_naive.py — converts a naive+https:// share URI into a
klzgrad naive config.json (SOCKS5 listen + naive proxy).
Run with: `pytest infra/naive/test_parse_naive.py -v`
"""
import pytest
from parse_naive import build_config, parse_naive_proxy

U, P, H, PORT = "user", "secret", "example.com", 443


def test_https_strips_prefix_and_fragment():
    url = f"naive+https://{U}:{P}@{H}:{PORT}#myproxy"
    assert parse_naive_proxy(url) == f"https://{U}:{P}@{H}:{PORT}"


def test_quic_scheme_preserved():
    url = f"naive+quic://{U}:{P}@{H}:{PORT}"
    assert parse_naive_proxy(url) == f"quic://{U}:{P}@{H}:{PORT}"


def test_query_and_fragment_dropped():
    url = f"naive+https://{U}:{P}@{H}:{PORT}?padding=true#node"
    assert parse_naive_proxy(url) == f"https://{U}:{P}@{H}:{PORT}"


def test_no_port_kept_verbatim():
    url = f"naive+https://{U}:{P}@{H}"
    assert parse_naive_proxy(url) == f"https://{U}:{P}@{H}"


def test_percent_encoded_password_preserved():
    url = f"naive+https://{U}:p%40ss@{H}:{PORT}"
    assert parse_naive_proxy(url) == f"https://{U}:p%40ss@{H}:{PORT}"


def test_rejects_missing_prefix():
    with pytest.raises(ValueError):
        parse_naive_proxy(f"https://{U}:{P}@{H}:{PORT}")


def test_rejects_empty():
    with pytest.raises(ValueError):
        parse_naive_proxy("")


def test_rejects_bad_scheme():
    with pytest.raises(ValueError):
        parse_naive_proxy(f"naive+ws://{U}:{P}@{H}:{PORT}")


def test_rejects_missing_host():
    with pytest.raises(ValueError):
        parse_naive_proxy(f"naive+https://{U}:{P}@")


def test_rejects_missing_credentials():
    with pytest.raises(ValueError):
        parse_naive_proxy(f"naive+https://{H}:{PORT}")


def test_build_config_wraps_with_socks_listen():
    cfg = build_config(f"naive+https://{U}:{P}@{H}:{PORT}#x", socks_port=1080)
    assert cfg["listen"] == "socks://0.0.0.0:1080"
    assert cfg["proxy"] == f"https://{U}:{P}@{H}:{PORT}"


def test_build_config_custom_port():
    cfg = build_config(f"naive+https://{U}:{P}@{H}:{PORT}", socks_port=10800)
    assert cfg["listen"] == "socks://0.0.0.0:10800"
