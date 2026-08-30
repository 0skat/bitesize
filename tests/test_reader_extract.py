import trafilatura

import reader_extract

ARTICLE_BODY = "This is the real article body sentence. " * 60

OVERLAY_FIXTURE = (
    """
<html><head><title>Story</title></head><body>
<header><nav>Home Politics Sports</nav></header>
<div class="paywall-overlay">
  <p>Assine agora para continuar lendo. Oferta especial por tempo limitado.</p>
</div>
<article><p>"""
    + ARTICLE_BODY
    + """</p></article>
<footer>Copyright 2026</footer>
</body></html>
"""
).encode("utf-8")


def test_extract_article_text_prefers_long_article_over_overlay():
    text = reader_extract.extract_article_text(OVERLAY_FIXTURE)
    assert "real article body" in text
    assert "Assine agora" not in text
    assert len(text) >= 180


def test_extract_article_text_matches_or_beats_trafilatura_baseline():
    baseline = trafilatura.extract(OVERLAY_FIXTURE, no_fallback=False) or ""
    text = reader_extract.extract_article_text(OVERLAY_FIXTURE)
    assert len(text) >= len(baseline) * 0.9


def test_extract_article_text_empty_input_returns_empty_string():
    assert reader_extract.extract_article_text(b"") == ""
    assert reader_extract.extract_article_text(None) == ""


def test_extract_article_text_handles_malformed_html_without_raising():
    text = reader_extract.extract_article_text(b"<html><body><p>broken")
    assert isinstance(text, str)


def test_extract_article_text_strips_tags_and_collapses_whitespace():
    html = b"<html><body><article><p>Hello   world.\n\nSecond   line.</p></article></body></html>"
    text = reader_extract.extract_article_text(html)
    assert "<p>" not in text
    assert "  " not in text
