"""Parse a naive+https:// (or naive+quic://) share URI into a klzgrad naive
config.json (SOCKS5 listen + naive proxy outbound).

The operator's NaïveProxy account is shared as
`naive+https://user:pass@host:port#name` (the sing-box / NekoBox share format).
The `naive+` prefix only tags the protocol; the remainder is exactly naive's
`proxy` URL. Padding is automatic (negotiated by the CONNECT padding header), so
no query parameters are carried into the config.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

_PREFIX = "naive+"
_ALLOWED_SCHEMES = ("https", "quic")


def parse_naive_proxy(url: str) -> str:
    """Convert a naive+https:// / naive+quic:// share URI to a naive proxy URL."""
    if not url or not url.startswith(_PREFIX):
        raise ValueError(f"not a naive+ URI: {url!r}")

    # Strip the protocol tag; drop the #fragment (display name) and ?query
    # (no client-relevant params). Keep userinfo verbatim to preserve any
    # percent-encoding in the password.
    proxy = url[len(_PREFIX):].split("#", 1)[0].split("?", 1)[0]

    parsed = urlparse(proxy)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"unsupported naive scheme {parsed.scheme!r} in {url!r}")
    if not parsed.hostname:
        raise ValueError(f"missing host in {url!r}")
    if not parsed.username:
        raise ValueError(f"missing credentials in {url!r}")
    return proxy


def build_config(naive_url: str, *, socks_port: int = 1080) -> dict:
    """Build a klzgrad naive client config: SOCKS5 listen + naive proxy."""
    return {
        "listen": f"socks://0.0.0.0:{socks_port}",
        "proxy": parse_naive_proxy(naive_url),
    }


if __name__ == "__main__":  # pragma: no cover
    import os
    import sys

    url = os.environ.get("TG_NAIVE_URL", "").strip()
    out_path = os.environ.get("NAIVE_CONFIG_PATH", "/etc/naive/config.json")
    if not url:
        sys.stderr.write("TG_NAIVE_URL is empty — cannot build naive config.\n")
        sys.exit(2)
    cfg = build_config(url)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    sys.stderr.write(f"wrote naive config to {out_path}\n")
