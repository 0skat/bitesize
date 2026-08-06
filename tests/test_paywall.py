from unittest.mock import MagicMock, patch

import paywall


def test_fetch_with_paywall_bypass_direct_success(monkeypatch):
    paywall.reset_stats()

    def fake_download(url, quiet=False):
        if "archive" not in url:
            return b"<html><body>" + b"x" * 300 + b"</body></html>"
        return None

    monkeypatch.setattr("feed._download_url", fake_download)
    monkeypatch.setattr(paywall, "_extract_text", lambda _: "x" * 300)

    text, source = paywall.fetch_with_paywall_bypass("https://example.com/a")
    assert len(text) >= 180
    assert source == "direct"
    stats = paywall.snapshot_stats()
    assert stats["direct_success"] == 1
    assert stats["mirror_success"] == 0


def test_fetch_with_paywall_bypass_uses_mirror(monkeypatch):
    paywall.reset_stats()

    def fake_download(url, quiet=False):
        if "archive.is" in url:
            return b"<html><body>" + b"y" * 300 + b"</body></html>"
        return b"<html><body>short</body></html>"

    monkeypatch.setattr("feed._download_url", fake_download)
    monkeypatch.setattr(
        paywall,
        "_extract_text",
        lambda raw: "y" * 300 if b"y" * 10 in raw else "short",
    )

    text, source = paywall.fetch_with_paywall_bypass("https://paywall.example/a")
    assert source == "archive.is"
    assert len(text) >= 180


def test_mirror_urls_match_shortcut_patterns():
    url = "https://news.example/story"
    built = dict((name, fn(url)) for name, fn in paywall.MIRRORS)
    assert built["archive.is"] == f"https://archive.is/newest/{url}"
    assert built["1ft.io"] == f"https://1ft.io/{url}"
    assert built["archive.org"] == f"https://web.archive.org/web/2/{url}"
    assert "removepaywall.com/search?url=" in built["removepaywall.com"]


def test_format_summary_includes_rates():
    paywall.reset_stats()
    paywall._record_article()
    paywall._record_direct(attempt=True, success=True)
    summary = paywall.format_summary()
    assert "Paywall fetch:" in summary
    assert "%" in summary
