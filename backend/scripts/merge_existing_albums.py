"""CLI entrypoint for merging pre-existing sibling Post-rows into single
album-style Posts.

Run inside the ingester container once after deploying the schema
change that adds Post.tg_grouped_id:

    docker compose exec ingester python -m scripts.merge_existing_albums
"""
from __future__ import annotations

import asyncio

from ingester.merge_existing_albums import _run_from_cli


if __name__ == "__main__":
    asyncio.run(_run_from_cli())
