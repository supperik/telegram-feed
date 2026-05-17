from datetime import timedelta
from unittest.mock import MagicMock

from api.presign import presigned_get


def test_presigned_get_uses_client_with_bucket_and_key() -> None:
    client = MagicMock()
    client.presigned_get_object.return_value = "https://minio/example.jpg?sig=abc"

    url = presigned_get(client, bucket="media", key="photos/1/2.jpg", expires_seconds=3600)

    assert url == "https://minio/example.jpg?sig=abc"
    args, kwargs = client.presigned_get_object.call_args
    assert args[0] == "media"
    assert args[1] == "photos/1/2.jpg"
    assert kwargs["expires"] == timedelta(seconds=3600)
