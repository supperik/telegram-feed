import os

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

from shared.config import Settings

_MTPROXY_EMPTY_SECRET = "00000000000000000000000000000000"


def make_client(settings: Settings, *, sessions_dir: str = "/app/sessions") -> TelegramClient:
    """Construct a TelegramClient for the userbot session.

    Ensures `sessions_dir` exists. The session file lives at
    `<sessions_dir>/<settings.tg_session_name>`; Telethon appends `.session`
    automatically.

    Proxy modes:
    - ``tg_proxy_type == "mtproxy"``: configures
      ``ConnectionTcpMTProxyRandomizedIntermediate`` and a ``(host, port, secret)``
      proxy tuple.
    - ``tg_proxy_type == "socks5"``: passes Telethon's canonical SOCKS5 dict
      (``{proxy_type, addr, port, rdns}``) — meant to talk to the naive sidecar
      (default) or the xray/VLESS sidecar (fallback). No ``connection=`` override.
    - else: direct MTProto connection.
    """
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, settings.tg_session_name)

    kwargs: dict = {}
    if settings.tg_proxy_type == "mtproxy":
        kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
        kwargs["proxy"] = (
            settings.tg_proxy_host,
            settings.tg_proxy_port,
            settings.tg_proxy_secret or _MTPROXY_EMPTY_SECRET,
        )
    elif settings.tg_proxy_type == "socks5":
        kwargs["proxy"] = {
            "proxy_type": "socks5",
            "addr": settings.tg_proxy_host,
            "port": settings.tg_proxy_port,
            "rdns": True,
        }
    return TelegramClient(session_path, settings.tg_api_id, settings.tg_api_hash, **kwargs)
