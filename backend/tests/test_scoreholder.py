"""Tests for app.scoreholder URL extraction."""

import pytest

from app.scoreholder import extract_event_id


class TestExtractEventId:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://scoreholder.com/en/events/66c6ae8a8026be8951720d23", "66c6ae8a8026be8951720d23"),
            ("https://scoreholder.com/events/66c6ae8a8026be8951720d23", "66c6ae8a8026be8951720d23"),
            ("https://scoreholder.com/api/events/66c6ae8a8026be8951720d23?scope=PUBLIC", "66c6ae8a8026be8951720d23"),
            ("https://scoreholder.com/en/events/66c6ae8a8026be8951720d23?tab=results", "66c6ae8a8026be8951720d23"),
            ("https://scoreholder.com/en/events/66c6ae8a8026be8951720d23/overview", "66c6ae8a8026be8951720d23"),
        ],
    )
    def test_valid_urls(self, url, expected):
        assert extract_event_id(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "not a url",
            "https://example.com/foo",
            "https://scoreholder.com/en/events/",
            "https://scoreholder.com/en/events/shortid",
            "https://scoreholder.com",
        ],
    )
    def test_invalid_urls(self, url):
        assert extract_event_id(url) is None
