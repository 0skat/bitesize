"""Readability-style extract on already-downloaded HTML.

Trafilatura (`paywall._extract_text`) scores nodes with its own rule set.
This module runs a Mozilla-Readability-class pass (`readability-lxml`) on
the *same bytes* as an alternative, so `scripts/measure_reader_extract.py`
can compare the two before either becomes the default fetch path.

This is a static-HTML extractor: it never runs page JavaScript, never loads
a browser, and never touches cookies or login state. See
docs/research/2026-08-30-safari-reader-paywall.md for why that means it
cannot recover text the server never sent.
"""

from __future__ import annotations

import lxml.html
from readability import Document


def extract_article_text(html: bytes | str | None) -> str:
    """Return the main article text readability-lxml finds in `html`.

    Returns "" on empty input or any parse failure (never raises), matching
    the failure behavior of `paywall._extract_text`.
    """
    if not html:
        return ""
    try:
        summary_html = Document(html).summary(html_partial=True)
    except Exception:
        return ""
    if not summary_html:
        return ""
    try:
        tree = lxml.html.fromstring(summary_html)
    except Exception:
        return ""
    text = tree.text_content() or ""
    return " ".join(text.split()).strip()
