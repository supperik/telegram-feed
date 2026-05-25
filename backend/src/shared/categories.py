from __future__ import annotations

from typing import Final

CHANNEL_CATEGORIES: Final[tuple[tuple[str, str], ...]] = (
    ("news", "Новости"),
    ("tech", "Технологии"),
    ("business", "Бизнес"),
    ("entertainment", "Развлечения"),
    ("sports", "Спорт"),
    ("education", "Образование"),
)

CATEGORY_SLUGS: Final[frozenset[str]] = frozenset(slug for slug, _ in CHANNEL_CATEGORIES)
