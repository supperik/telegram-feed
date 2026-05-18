"""Tests for parse_vless.py — Python parser that converts a vless:// URL
into an xray-core JSON config (SOCKS5 inbound + VLESS outbound).
Run with: `pytest infra/xray/test_parse_vless.py -v`
"""
import pytest

from parse_vless import build_config, parse_vless_outbound


UUID = "550e8400-e29b-41d4-a716-446655440000"


def test_parse_simple_tcp_tls_url():
    url = (
        f"vless://{UUID}@example.com:443"
        "?security=tls&sni=example.com&type=tcp&encryption=none"
        "#myserver"
    )
    out = parse_vless_outbound(url)
    assert out["protocol"] == "vless"
    assert out["tag"] == "vless-out"
    vnext = out["settings"]["vnext"][0]
    assert vnext["address"] == "example.com"
    assert vnext["port"] == 443
    user = vnext["users"][0]
    assert user["id"] == UUID
    assert user["encryption"] == "none"
    assert user["flow"] == ""
    ss = out["streamSettings"]
    assert ss["network"] == "tcp"
    assert ss["security"] == "tls"
    assert ss["tlsSettings"]["serverName"] == "example.com"
    assert ss["tlsSettings"]["allowInsecure"] is False


def test_parse_xhttp_with_path_and_host():
    url = (
        f"vless://{UUID}@1.2.3.4:8443"
        "?security=tls&sni=cdn.example.com&type=xhttp"
        "&path=%2Fws-tunnel&host=cdn.example.com&mode=packet-up"
        "&fp=chrome&alpn=h2%2Chttp%2F1.1"
        "#xhttp-node"
    )
    out = parse_vless_outbound(url)
    vnext = out["settings"]["vnext"][0]
    assert vnext["address"] == "1.2.3.4"
    assert vnext["port"] == 8443
    ss = out["streamSettings"]
    assert ss["network"] == "xhttp"
    assert ss["security"] == "tls"
    assert ss["tlsSettings"]["serverName"] == "cdn.example.com"
    assert ss["tlsSettings"]["fingerprint"] == "chrome"
    assert ss["tlsSettings"]["alpn"] == ["h2", "http/1.1"]
    # XHTTP-specific stream settings.
    xhttp = ss["xhttpSettings"]
    assert xhttp["path"] == "/ws-tunnel"
    assert xhttp["host"] == "cdn.example.com"
    assert xhttp["mode"] == "packet-up"


def test_parse_reality_vision():
    url = (
        f"vless://{UUID}@1.2.3.4:443"
        "?security=reality&sni=www.microsoft.com&type=tcp"
        "&flow=xtls-rprx-vision&fp=chrome"
        "&pbk=PUBKEY_BASE64&sid=01ab"
        "#reality-node"
    )
    out = parse_vless_outbound(url)
    user = out["settings"]["vnext"][0]["users"][0]
    assert user["flow"] == "xtls-rprx-vision"
    ss = out["streamSettings"]
    assert ss["security"] == "reality"
    assert ss["realitySettings"]["serverName"] == "www.microsoft.com"
    assert ss["realitySettings"]["fingerprint"] == "chrome"
    assert ss["realitySettings"]["publicKey"] == "PUBKEY_BASE64"
    assert ss["realitySettings"]["shortId"] == "01ab"


def test_parse_rejects_non_vless_url():
    with pytest.raises(ValueError):
        parse_vless_outbound("vmess://abc")


def test_parse_rejects_empty_url():
    with pytest.raises(ValueError):
        parse_vless_outbound("")


def test_parse_rejects_missing_uuid():
    with pytest.raises(ValueError):
        parse_vless_outbound("vless://@example.com:443")


def test_build_config_wraps_outbound_with_socks_inbound():
    url = f"vless://{UUID}@example.com:443?security=tls&type=tcp#x"
    cfg = build_config(url, socks_port=1080)
    inb = cfg["inbounds"][0]
    assert inb["protocol"] == "socks"
    assert inb["port"] == 1080
    assert inb["listen"] == "0.0.0.0"
    assert inb["settings"]["auth"] == "noauth"
    assert cfg["outbounds"][0]["protocol"] == "vless"


def test_build_config_custom_socks_port():
    url = f"vless://{UUID}@example.com:443?security=tls&type=tcp#x"
    cfg = build_config(url, socks_port=10800)
    assert cfg["inbounds"][0]["port"] == 10800
