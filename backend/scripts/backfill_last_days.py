"""CLI entrypoint: backfill the last N days of posts for active channels.

A manual recovery tool for filling a gap after the ingester was down longer
than boot catchup can cover. Idempotent — safe to run next to the live
ingester and safe to re-run.

Run inside the ingester container once the userbot is healthy:

    docker compose exec ingester python -m scripts.backfill_last_days --days 8
    docker compose exec ingester python -m scripts.backfill_last_days --days 8 --channel 12
"""
from __future__ import annotations

import asyncio

from ingester.last_days_backfill import _run_from_cli


if __name__ == "__main__":
    asyncio.run(_run_from_cli())
