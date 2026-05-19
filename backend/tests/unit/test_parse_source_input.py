from __future__ import annotations

import pytest

from api.parse_source_input import ParseError, ParsedSource, parse_source_input


class TestPublicUsername:
    def test_bare_username(self):
        assert parse_source_input("durov") == ParsedSource(kind="public_username", username="durov")

    def test_with_at(self):
        assert parse_source_input("@Durov") == ParsedSource(kind="public_username", username="durov")

    def test_with_t_me(self):
        assert parse_source_input("t.me/durov") == ParsedSource(kind="public_username", username="durov")

    def test_with_https(self):
        assert parse_source_input("https://t.me/durov") == ParsedSource(
            kind="public_username", username="durov"
        )

    def test_trailing_slash(self):
        assert parse_source_input("https://t.me/durov/") == ParsedSource(
            kind="public_username", username="durov"
        )


class TestPrivateInvite:
    def test_short_plus(self):
        assert parse_source_input("https://t.me/+abcDEF_123") == ParsedSource(
            kind="private_invite", invite_hash="abcDEF_123"
        )

    def test_legacy_joinchat(self):
        assert parse_source_input("https://t.me/joinchat/abcDEF-_123") == ParsedSource(
            kind="private_invite", invite_hash="abcDEF-_123"
        )

    def test_without_protocol(self):
        assert parse_source_input("t.me/+abc") == ParsedSource(
            kind="private_invite", invite_hash="abc"
        )


class TestInvalid:
    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "ab",                       # too short for username (min 5)
            "x" * 200,
            "не_ascii_кириллица",
            "https://example.com/foo",
            "https://t.me/",
            "https://t.me/durov?param=1",
        ],
    )
    def test_invalid_inputs(self, raw):
        with pytest.raises(ParseError):
            parse_source_input(raw)


class TestWhitespace:
    def test_strips_surrounding(self):
        assert parse_source_input("  @durov  ") == ParsedSource(
            kind="public_username", username="durov"
        )
