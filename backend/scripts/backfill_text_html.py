"""CLI entrypoint for refilling Post.text_html on existing rows.

Run inside the ingester container after deploying the entities → HTML
ingester change:

    docker compose exec ingester python -m scripts.backfill_text_html
"""
from __future__ import annotations

import asyncio

from ingester.backfill_text_html import _run_from_cli


if __name__ == "__main__":
    asyncio.run(_run_from_cli())
