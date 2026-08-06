from unittest.mock import MagicMock, patch

import feed


SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test</title>
<item><title>Story One</title><link>https://example.com/1</link>
<description><![CDATA[<p>Body one</p>]]></description></item>
</channel></rss>"""


def test_fetch_feed_uses_downloaded_bytes(monkeypatch):
    monkeypatch.setattr(feed, "_download_url", lambda url: SAMPLE_RSS)
    articles = feed.fetch_feed("Test Source", "https://example.com/feed.xml")
    assert len(articles) == 1
    assert articles[0]["title"] == "Story One"
    assert articles[0]["source"] == "Test Source"


def test_fetch_feed_returns_empty_when_download_fails(monkeypatch):
    monkeypatch.setattr(feed, "_download_url", lambda url: None)
    articles = feed.fetch_feed("Test Source", "https://example.com/feed.xml")
    assert articles == []


@patch("feed.requests.get")
def test_download_url_uses_certifi(mock_get):
    mock_get.return_value = MagicMock(
        content=b"ok",
        raise_for_status=MagicMock(),
    )
    result = feed._download_url("https://example.com/rss")
    assert result == b"ok"
    mock_get.assert_called_once()
    _, kwargs = mock_get.call_args
    assert kwargs["verify"] is not None
