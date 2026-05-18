"""Parse a vless:// URL into an xray-core JSON config.

Supported transports: tcp (default), xhttp.
Supported security: tls (default), reality, none.

Reference URL format:
  vless://<uuid>@<host>:<port>?<query>#<remark>

Common query params used:
  encryption, flow, type (network), security, sni, fp (fingerprint),
  pbk (Reality public key), sid (Reality short id), alpn, allowInsecure,
  path, host, mode (xhttp parameters).
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


def parse_vless_outbound(url: str) -> dict[str, Any]:
    """Parse a vless:// URL into an xray outbound config dict."""
    if not url or not url.startswith("vless://"):
        raise ValueError(f"not a vless:// URL: {url!r}")

    parsed = urlparse(url)
    uuid = unquote(parsed.username or "")
    host = parsed.hostname or ""
    port = parsed.port or 443
    if not uuid or not host:
        raise ValueError(f"missing uuid or host in {url!r}")

    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}

    network = q.get("type", "tcp")
    security = q.get("security", "tls")
    flow = q.get("flow", "")
    encryption = q.get("encryption", "none")

    stream: dict[str, Any] = {"network": network, "security": security}
    if security == "tls":
        stream["tlsSettings"] = {
            "serverName": q.get("sni", host),
            "allowInsecure": q.get("allowInsecure", "0") in ("1", "true"),
        }
        if "fp" in q:
            stream["tlsSettings"]["fingerprint"] = q["fp"]
        if "alpn" in q:
            stream["tlsSettings"]["alpn"] = q["alpn"].split(",")
    elif security == "reality":
        stream["realitySettings"] = {
            "serverName": q.get("sni", host),
            "publicKey": q.get("pbk", ""),
            "shortId": q.get("sid", ""),
            "fingerprint": q.get("fp", "chrome"),
        }
        if "spx" in q:
            stream["realitySettings"]["spiderX"] = q["spx"]

    if network == "xhttp":
        stream["xhttpSettings"] = {
            "path": q.get("path", "/"),
            "host": q.get("host", ""),
            "mode": q.get("mode", "auto"),
        }

    return {
        "tag": "vless-out",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [
                        {"id": uuid, "encryption": encryption, "flow": flow}
                    ],
                }
            ]
        },
        "streamSettings": stream,
    }


def build_config(vless_url: str, *, socks_port: int = 1080) -> dict[str, Any]:
    """Build a full xray client config: SOCKS5 inbound + VLESS outbound."""
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "0.0.0.0",
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [parse_vless_outbound(vless_url)],
    }


if __name__ == "__main__":  # pragma: no cover
    import os
    import sys

    url = os.environ.get("TG_VLESS_URL", "").strip()
    out_path = os.environ.get("XRAY_CONFIG_PATH", "/etc/xray/config.json")
    if not url:
        sys.stderr.write("TG_VLESS_URL is empty — cannot build xray config.\n")
        sys.exit(2)
    cfg = build_config(url)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    sys.stderr.write(f"wrote xray config to {out_path}\n")
