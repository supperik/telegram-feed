import pytest

from shared.utils.masks import mask_invite_hash


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("abcDEF1234567", "abcD…67"),
        ("ABCDEFGH", "ABCD…GH"),
        ("short", "***"),
        ("", "***"),
        (None, "***"),
        ("1234567", "***"),       # 7 chars — below threshold
        ("12345678", "1234…78"),  # 8 chars — at threshold
    ],
)
def test_mask_invite_hash(raw, expected):
    assert mask_invite_hash(raw) == expected
