"""Test double for telethon.TelegramClient used by ingester e2e tests.

Duck-typed (NOT a subclass of TelegramClient). Implements the surface
that `ingester.live`, `ingester.photos`, and `ingester.normalize`
actually call:

  - add_event_handler / get_entity / iter_messages / download_media /
    download_profile_photo / start / disconnect / get_me
  - emit_new_message(msg, chat_id) to deliver a synthetic NewMessage
    event to every handler registered with an events.NewMessage builder.

Companion helpers `make_fake_message` and `make_fake_photo` build the
attribute-bag objects that `normalize_message` and `download_and_store_photo`
expect.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

HandlerEntry = tuple[Callable[..., Awaitable[None]], str]


class FakeTelethonClient:
    """Duck-typed stand-in for telethon.TelegramClient.

    Configuration knobs (set by the test before driving the client):

    - `entities` : dict[chat_id -> entity-stub] returned by get_entity.
    - `catchup_messages` : dict[chat_id -> list[msg]] iterated by iter_messages.
    - `download_payloads` : dict[file_key -> bytes] returned by download_media.
      Key is `getattr(target, 'id', None)` for raw photo/video objects or
      `(msg.id, thumb_index)` when called with `thumb=...`.
    - `profile_photos` : dict[entity.id -> bytes|None] for download_profile_photo.
    """

    def __init__(self) -> None:
        self.entities: dict[int, Any] = {}
        self.catchup_messages: dict[int, list[Any]] = {}
        self.download_payloads: dict[Any, bytes] = {}
        self.profile_photos: dict[int, bytes | None] = {}
        self._handlers: list[HandlerEntry] = []
        self.calls: list[Any] = []  # __call__'d telethon requests

    def add_event_handler(self, handler: Callable[..., Awaitable[None]], builder: Any) -> None:
        self._handlers.append((handler, type(builder).__name__))

    async def emit_new_message(self, msg: Any, chat_id: int) -> None:
        """Synthesise a NewMessage event and await every NewMessage handler."""
        event = SimpleNamespace(chat_id=chat_id, message=msg)
        for handler, builder_name in self._handlers:
            if builder_name == "NewMessage":
                await handler(event)

    async def start(self, phone: str | None = None) -> FakeTelethonClient:
        return self

    async def disconnect(self) -> None:
        return None

    async def get_me(self) -> SimpleNamespace:
        return SimpleNamespace(id=0, username="fake_ingester")

    async def __call__(self, request: Any) -> Any:
        self.calls.append(request)
        return None

    async def get_entity(self, ident: Any) -> Any:
        """Return the entity stub registered for `ident`. `ident` may be a
        positive raw chat id (int) — as stored in Channel.tg_chat_id — or
        a telethon.tl.types.PeerChannel wrapping that id, as catchup_channels
        does to disambiguate channels from users.

        The fake normalises both to the positive int key so callers can
        register entities with `fake.entities[positive_id] = stub`.
        """
        key = getattr(ident, "channel_id", ident)
        return self.entities.get(key, SimpleNamespace(id=key))

    async def iter_messages(
        self,
        entity: Any,
        *,
        min_id: int = 0,
        max_id: int = 0,
        limit: int = 200,
        **_: Any,
    ):
        """Async-iterate self.catchup_messages[entity.id], filtered by min_id
        (id > min_id) and max_id (id < max_id; 0 = no upper bound), capped by
        limit. Mirrors Telethon: max_id excludes messages with id >= max_id.
        Yields in seeded list order — seed newest-first for backfill tests."""
        key = getattr(entity, "id", entity)
        msgs = list(self.catchup_messages.get(key, []))
        yielded = 0
        for m in msgs:
            if int(m.id) <= int(min_id):
                continue
            if max_id and int(m.id) >= int(max_id):
                continue
            if yielded >= limit:
                break
            yield m
            yielded += 1

    async def download_media(
        self,
        target: Any,
        file: Any = None,
        *,
        thumb: Any = None,
    ) -> bytes:
        """Return the pre-seeded payload for this media unit.

        Key lookup order:
          1. (target.id, thumb) when thumb is not None
          2. target.id (photo or video object)
          3. raw target if it's the dict key (escape hatch for unusual cases)
        Falls back to empty bytes — that mirrors Telethon's behaviour when a
        FILE_REFERENCE_EXPIRED or download failure occurs.
        """
        if thumb is not None and hasattr(target, "id"):
            payload = self.download_payloads.get((target.id, thumb))
            if payload is not None:
                return payload
        tid = getattr(target, "id", None)
        if tid is not None:
            payload = self.download_payloads.get(tid)
            if payload is not None:
                return payload
        return self.download_payloads.get(target, b"")

    async def download_profile_photo(self, entity: Any, file: Any = None) -> bytes | None:
        eid = getattr(entity, "id", entity)
        return self.profile_photos.get(eid)


def make_fake_photo(
    *,
    photo_id: int,
    w: int = 1280,
    h: int = 720,
) -> SimpleNamespace:
    """Minimal photo object: enough for normalize._largest_photo_size and
    download_and_store_photo (which uses photo.id and photo.sizes)."""
    return SimpleNamespace(
        id=photo_id,
        sizes=[SimpleNamespace(w=w, h=h)],
    )


def make_fake_message(
    *,
    id: int,
    text: str | None = None,
    photo: SimpleNamespace | None = None,
    grouped_id: int | None = None,
    date: datetime | None = None,
) -> SimpleNamespace:
    """Build the attribute-bag a Telethon Message exposes to normalize_message.

    Only fields normalize_message / photos / live actually read are present.
    `entities` is always None — entities_to_html accepts None and returns the
    plain text unchanged.
    """
    return SimpleNamespace(
        id=id,
        date=date or datetime.now(UTC),
        message=text,
        text=text,
        entities=None,
        edit_date=None,
        views=None,
        forwards=None,
        photo=photo,
        video=None,
        document=None,
        grouped_id=grouped_id,
    )
