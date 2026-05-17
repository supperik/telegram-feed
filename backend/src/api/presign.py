from __future__ import annotations

from datetime import timedelta

from minio import Minio


def presigned_get(client: Minio, *, bucket: str, key: str, expires_seconds: int) -> str:
    return client.presigned_get_object(bucket, key, expires=timedelta(seconds=expires_seconds))
