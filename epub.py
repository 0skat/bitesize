import html
import re
from datetime import datetime
from pathlib import Path

from ebooklib import epub

from config import INDEX_ENTRIES_PER_PAGE, MIN_BODY_CHARS, OUTPUT_DIR, TOP_PICKS_ON_COVER
from gemini import article_relevance

_CSS = """
/* Kindle-friendly typography — all sizes in em so the device font slider works */
html {
  font-size: 100%;
  -webkit-text-size-adjust: 100%;
}

@page {
  margin: 5%;
}

body {
  font-family: "Bookerly", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
  font-size: 1em;
  line-height: 1.65;
  color: #1a1a1a;
  margin: 0;
  padding: 0 4%;
  text-align: left;
  -webkit-hyphens: auto;
  hyphens: auto;
}

h1, h2, h3, h4 {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.25;
  font-weight: bold;
  hyphens: none;
  -webkit-hyphens: none;
}

h1 {
  font-size: 1.55em;
  border-bottom: 0.12em solid #333;
  padding-bottom: 0.3em;
  margin: 0 0 0.9em 0;
}

h2 { font-size: 1.3em; margin: 0.4em 0 0.5em 0; }
h3 { font-size: 1.12em; margin: 0 0 0.25em 0; }
h4 { font-size: 1em; margin: 0 0 0.2em 0; }

p { margin: 0 0 0.75em 0; text-align: justify; }

a { color: #1a5276; text-decoration: none; }

/* ── Global cover (matches article rhythm: kicker → headline → lead → blocks) ─ */
.global-cover-header { margin-bottom: 0.2em; }
.cover-lead {
  font-size: 1.02em;
  color: #333;
  line-height: 1.7;
  margin: 0 0 0.5em 0;
  text-align: left;
}
.cover-rule {
  border: none;
  border-top: 0.08em solid #bbb;
  margin: 1em 0 1.1em 0;
}
.cover-highlights { margin-top: 0.2em; }
.cover-highlights .lead-story {
  margin-bottom: 1em;
  padding: 0.65em 0 0.85em 0;
}
.cover-highlights .lead-story:last-child { margin-bottom: 0; }
.cover-highlights .lead-story .article-section { margin-bottom: 0.45em; }
.cover-highlights .lead-story h4 {
  font-size: 1em;
  font-weight: bold;
  margin: 0 0 0.35em 0;
  line-height: 1.3;
  text-align: left;
}
.cover-highlights .lead-story p {
  font-size: 0.95em;
  color: #444;
  line-height: 1.6;
  margin: 0;
  text-align: left;
}
.cover-highlights .lead-story:first-child {
  border-top: none;
  padding-top: 0;
}

/* ── Section cover pages ──────────────────────────────────────────────────── */
.cat-cover { text-align: center; margin-top: 12%; }
.cat-title {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.85em;
  color: #777;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  margin: 0 0 0.5em 0;
}
.cat-headline {
  font-size: 1.65em;
  font-weight: bold;
  margin: 0.35em 0 0.7em 0;
  line-height: 1.2;
  text-align: left;
}
.editorial {
  font-size: 1em;
  color: #444;
  margin: 0 0 1.2em 0;
  line-height: 1.65;
  text-align: left;
}
.lead-story {
  margin-bottom: 0.7em;
  padding: 0.55em 0;
  border-top: 0.06em solid #ccc;
  text-align: left;
}
.lead-story h4 { font-size: 0.98em; }
.lead-story p  { font-size: 0.9em; color: #555; margin: 0; text-align: left; }

/* ── Section index (table of contents per category) ───────────────────────── */
.section-index { margin-top: 0.5em; }
.section-index-intro {
  font-size: 0.88em;
  color: #666;
  margin-bottom: 1.2em;
  text-align: left;
}
.index-entry {
  margin-bottom: 1em;
  padding-bottom: 0.8em;
  border-bottom: 0.06em solid #ddd;
}
a.index-entry-link:last-of-type .index-entry { border-bottom: none; }
.index-num {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.72em;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 0.15em 0;
}
.index-title {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 1.05em;
  font-weight: bold;
  margin: 0 0 0.2em 0;
  line-height: 1.3;
  color: #1a1a1a;
}
a.index-entry-link {
  display: block;
  color: inherit;
  text-decoration: none;
}
a.index-entry-link .index-meta { color: #777; }
.index-meta { font-size: 0.75em; color: #777; margin: 0; text-align: left; }
.index-blurb {
  font-size: 0.88em;
  color: #444;
  margin: 0.35em 0 0 0;
  line-height: 1.5;
  text-align: left;
}
.index-page-nav {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.82em;
  color: #666;
  margin: 1.2em 0 0 0;
  padding-top: 0.8em;
  border-top: 0.06em solid #ccc;
  text-align: center;
}
.index-page-nav a { color: #1a5276; }

/* ── Individual articles ──────────────────────────────────────────────────── */
.article-header { margin-bottom: 1em; }
.article-section {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #888;
  margin: 0 0 0.35em 0;
}
.article-title {
  font-size: 1.35em;
  font-weight: bold;
  margin: 0 0 0.35em 0;
  line-height: 1.25;
}
.meta {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.75em;
  color: #666;
  margin: 0 0 0.8em 0;
  text-align: left;
}
.summary {
  font-size: 1.02em;
  color: #222;
  margin: 0 0 1em 0;
  line-height: 1.65;
  padding: 0.6em 0 0.6em 0.8em;
  border-left: 0.2em solid #bbb;
}
.summary-label {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #888;
  margin: 0 0 0.35em 0;
}
.summary-meta-line {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.72em;
  color: #666;
  margin: 0 0 0.55em 0;
  letter-spacing: 0.02em;
}
.index-relevance {
  font-size: 0.68em;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: #1b6b4d;
  margin: 0 0 0.35em 0;
  letter-spacing: 0.03em;
}
.top-picks { margin: 0.15em 0 0.85em 0; }
.top-picks-heading {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #666;
  margin: 0 0 0.55em 0;
}
a.top-pick-card {
  display: block;
  text-decoration: none;
  color: inherit;
  padding: 0.55em 0 0.75em 0;
  border-top: 0.06em solid #ccc;
}
a.top-pick-card:first-of-type {
  border-top: none;
  padding-top: 0;
}
.top-pick-meta {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #777;
  margin: 0 0 0.25em 0;
}
.top-pick-title {
  font-size: 1.02em;
  font-weight: bold;
  line-height: 1.25;
  margin: 0 0 0.3em 0;
  text-align: left;
}
.top-pick-blurb {
  font-size: 0.88em;
  color: #555;
  line-height: 1.45;
  margin: 0;
  text-align: left;
}
.article-body {
  font-size: 1em;
  color: #1a1a1a;
  margin-top: 0.5em;
}
.article-body p { margin: 0 0 0.75em 0; }
.article-body p:first-child::first-letter {
  font-size: 2.2em;
  float: left;
  line-height: 0.85;
  padding-right: 0.08em;
  font-weight: bold;
}
.read-more {
  font-size: 0.82em;
  margin-top: 1.2em;
  text-align: left;
}

/* ── Legacy multi-article page (kept for compatibility) ───────────────────── */
.article     { margin-bottom: 2em; padding-bottom: 1.2em; border-bottom: 0.06em solid #ddd; }

/* ── Fallback simple cover ────────────────────────────────────────────────── */
.cover     { text-align: center; margin-top: 18%; }
.c-title   { font-size: 2em; font-weight: bold; margin-bottom: 0.15em; }
.c-date    { font-size: 0.95em; color: #555; margin-bottom: 0.4em; }
.c-stats   { font-size: 0.85em; color: #888; }
.c-stats p { margin: 0.2em 0; text-align: center; }
.c-stats.cover-stats p {
  font-size: 0.95em;
  color: #444;
  text-align: left;
  margin: 0.45em 0;
  line-height: 1.5;
}
"""


def _e(s: str) -> str:
    return html.escape(s or "")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _xhtml_wrap(title: str, body: str) -> bytes:
    return (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html>"
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">'
        "<head>"
        f"  <title>{_e(title)}</title>"
        '  <meta charset="utf-8"/>'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>'
        '  <link href="style.css" rel="stylesheet" type="text/css"/>'
        "</head>"
        f"<body>{body}</body>"
        "</html>"
    ).encode("utf-8")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _article_blurb(art: dict) -> str:
    """Return an index blurb from the AI summary only — never raw body text."""
    summary = (art.get("summary") or "").strip()
    if not summary:
        return ""

    title_norm = _normalize_text(art.get("title", ""))
    summary_norm = _normalize_text(summary)
    if title_norm and summary_norm == title_norm:
        return ""
    if title_norm and summary_norm.startswith(title_norm):
        extra = summary_norm[len(title_norm):].strip(" .:-–—")
        if len(extra) < 40:
            return ""
    return summary


def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rsplit(" ", 1)[0] + "…"


def _fallback_section_cover(category: str, articles: list[dict]) -> dict:
    """Build a readable section cover when AI generation fails."""
    if not articles:
        return {}
    lead = articles[0]
    headline = _truncate(lead.get("title", category), 80)
    editorial = (
        f"{len(articles)} stories in {category} today."
        + (f" Lead: {_truncate(lead.get('summary') or lead['title'], 160)}" if lead else "")
    )
    top_stories = [
        {
            "title": art["title"],
            "one_liner": _truncate(art.get("summary") or art["title"], 120),
        }
        for art in articles[:3]
    ]
    return {"headline": headline, "editorial": editorial, "top_stories": top_stories}


def _fallback_global_cover(sections: dict[str, list]) -> dict:
    """Build a readable global cover when AI generation fails."""
    highlights: list[dict] = []
    lead_headline = "Today's digest"
    for category, articles in sections.items():
        if not articles:
            continue
        lead = articles[0]
        if not highlights:
            lead_headline = _truncate(lead.get("title") or category, 90)
        highlights.append({
            "section": category,
            "headline": _truncate(lead.get("title", ""), 100),
            "story": _truncate(lead.get("summary") or lead["title"], 160),
        })
    if not highlights:
        return {}
    return {
        "headline": lead_headline,
        "editorial": (
            f"Today's digest covers {sum(len(v) for v in sections.values())} stories "
            f"across {len(highlights)} sections."
        ),
        "highlights": highlights[:4],
    }


def _cover_highlight_xhtml(h: dict) -> str:
    """One section teaser on the global cover (mirrors in-article lead-story blocks)."""
    sec = _e(h.get("section", ""))
    hl_raw = (h.get("headline") or "").strip()
    story = _e(h.get("story", ""))
    parts = [
        '<div class="lead-story">',
        f'<p class="article-section">{sec}</p>',
    ]
    if hl_raw:
        parts.append(f"<h4>{_e(hl_raw)}</h4>")
    parts.append(f"<p>{story}</p></div>")
    return "".join(parts)


def _article_href(category: str, art: dict, sections: dict[str, list]) -> str | None:
    """Return spine filename for an article (must match generate_epub ordering)."""
    arts = sections.get(category) or []
    slug = _slugify(category)
    url = (art.get("url") or "").strip()
    title = (art.get("title") or "").strip()
    for i, a in enumerate(arts, start=1):
        if url and (a.get("url") or "").strip() == url:
            return f"article_{slug}_{i:02d}.xhtml"
        if not url and title and (a.get("title") or "").strip() == title:
            return f"article_{slug}_{i:02d}.xhtml"
    return None


def _top_picks_xhtml(sections: dict[str, list], limit: int) -> str:
    """Digest front page: highest-scoring items across all sections with deep links."""
    ranked: list[tuple[int, str, dict]] = []
    for cat, arts in sections.items():
        for a in arts or []:
            ranked.append((article_relevance(a), cat, a))
    ranked.sort(
        key=lambda x: (-x[0], (x[1] or "").lower(), (x[2].get("title") or "").lower()),
    )
    picks = ranked[:limit]
    if not picks:
        return ""
    parts: list[str] = [
        '<section class="top-picks">',
        '<h2 class="top-picks-heading">Top stories by relevance</h2>',
    ]
    for score, cat, art in picks:
        href = _article_href(cat, art, sections)
        if not href:
            continue
        blurb = _article_blurb(art)
        if not blurb:
            blurb = (art.get("summary") or art.get("title") or "").strip()
        blurb = _truncate(blurb, 160)
        parts.append(
            f'<a class="top-pick-card" href="{_e(href)}">'
            f'<div>'
            f'<p class="top-pick-meta">{_e(cat)} &middot; score {score}/100</p>'
            f'<h3 class="top-pick-title">{_e(art.get("title", ""))}</h3>'
            f'<p class="top-pick-blurb">{_e(blurb)}</p>'
            f"</div>"
            f"</a>"
        )
    parts.append("</section>")
    return "".join(parts)


def _body_paragraphs(text: str, drop_cap: bool = True) -> str:
    """Convert plain-text article body to XHTML paragraphs."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return ""
    parts = []
    for i, p in enumerate(paragraphs):
        cls = ' class="lede"' if drop_cap and i == 0 else ""
        parts.append(f"<p{cls}>{_e(p)}</p>")
    return "".join(parts)


def _article_body_html(art: dict) -> str:
    body = (art.get("content") or "").strip()
    summary = (art.get("summary") or "").strip()
    parts: list[str] = []

    if summary:
        rel = article_relevance(art)
        parts.append(
            f'<div class="summary">'
            f'<p class="summary-label">Summary</p>'
            f'<p class="summary-meta-line">Relevance score: {rel}/100</p>'
            f"<p>{_e(summary)}</p>"
            f"</div>"
        )

    if len(body) >= MIN_BODY_CHARS:
        parts.append(f'<div class="article-body">{_body_paragraphs(body)}</div>')
    elif body and not summary:
        parts.append(f'<div class="article-body">{_body_paragraphs(body, drop_cap=False)}</div>')

    return "".join(parts)


def _global_cover_xhtml(cover_data: dict, sections: dict[str, list], now: datetime) -> bytes:
    total = sum(len(v) for v in sections.values())
    date_str = now.strftime("%A, %B %d, %Y")
    top_picks_html = _top_picks_xhtml(sections, TOP_PICKS_ON_COVER)

    if not cover_data:
        cover_data = _fallback_global_cover(sections)

    if cover_data:
        headline = _e(cover_data.get("headline", ""))
        editorial = _e(cover_data.get("editorial", ""))
        highlights_html = "".join(
            _cover_highlight_xhtml(h) for h in cover_data.get("highlights", [])
        )
        kicker = f"News Digest &middot; {_e(date_str)} &middot; {total} articles"
        body = (
            f'<header class="article-header global-cover-header">'
            f'<p class="article-section">{kicker}</p>'
            f'<h1 class="article-title">{headline}</h1>'
            f'<p class="cover-lead">{editorial}</p>'
            f"</header>"
            f"{top_picks_html}"
            f'<hr class="cover-rule" />'
            f'<div class="cover-highlights">{highlights_html}</div>'
        )
    else:
        stats = "".join(
            f"<p>{_e(cat)} &middot; {len(arts)} articles</p>"
            for cat, arts in sections.items() if arts
        )
        kicker = f"News Digest &middot; {_e(date_str)} &middot; {total} articles"
        body = (
            f'<header class="article-header global-cover-header">'
            f'<p class="article-section">{kicker}</p>'
            f'<h1 class="article-title">News Digest</h1>'
            f'<p class="cover-lead">Your sections for this edition.</p>'
            f"</header>"
            f"{top_picks_html}"
            f'<hr class="cover-rule" />'
            f'<div class="c-stats cover-stats">{stats}</div>'
        )

    return _xhtml_wrap("News Digest", body)


def _section_cover_xhtml(category: str, cover_data: dict, articles: list[dict]) -> bytes:
    if not cover_data:
        cover_data = _fallback_section_cover(category, articles)

    if cover_data:
        headline  = _e(cover_data.get("headline", ""))
        editorial = _e(cover_data.get("editorial", ""))
        top_stories_html = "".join(
            f'<div class="lead-story">'
            f'<h4>{_e(s.get("title",""))}</h4>'
            f'<p>{_e(s.get("one_liner",""))}</p>'
            f"</div>"
            for s in cover_data.get("top_stories", [])
        )
        body = (
            f'<div class="cat-cover">'
            f'<p class="cat-title">{_e(category)}</p>'
            f'<h2 class="cat-headline">{headline}</h2>'
            f'<p class="editorial">{editorial}</p>'
            f"{top_stories_html}"
            f"</div>"
        )
    else:
        body = (
            f'<div class="cat-cover">'
            f'<p class="cat-title">{_e(category)}</p>'
            f"</div>"
        )

    return _xhtml_wrap(category, body)


def _index_page_filename(slug: str, page_num: int) -> str:
    if page_num == 1:
        return f"index_{slug}.xhtml"
    return f"index_{slug}_{page_num:02d}.xhtml"


def _section_index_entries_html(
    articles: list[dict],
    slug: str,
    start_num: int,
) -> str:
    entries = []
    for offset, art in enumerate(articles):
        story_num = start_num + offset
        art_slug = f"{slug}_{story_num:02d}"
        pub_tag = f" &middot; {art['published']}" if art.get("published") else ""
        blurb = _article_blurb(art)
        blurb_tag = f'<p class="index-blurb">{_e(blurb)}</p>' if blurb else ""
        score = article_relevance(art)
        score_line = f'<p class="index-relevance">Relevance {score}/100</p>'
        entries.append(
            f'<a class="index-entry-link" href="article_{art_slug}.xhtml">'
            f'<div class="index-entry">'
            f'<p class="index-num">Story {story_num}</p>'
            f"{score_line}"
            f'<h2 class="index-title">{_e(art["title"])}</h2>'
            f'<p class="index-meta">{_e(art["source"])}{pub_tag}</p>'
            f"{blurb_tag}"
            f"</div>"
            f"</a>"
        )
    return "".join(entries)


def _section_index_page_xhtml(
    category: str,
    page_articles: list[dict],
    slug: str,
    start_num: int,
    total: int,
    page_num: int,
    total_pages: int,
    prev_file: str | None,
    next_file: str | None,
) -> bytes:
    end_num = start_num + len(page_articles) - 1
    if total_pages == 1:
        intro = (
            f"{total} stories in this section, highest relevance first. "
            "Tap a card to open the full article."
        )
    else:
        intro = (
            f"Stories {start_num}–{end_num} of {total} in {category}. "
            f"Page {page_num} of {total_pages}."
        )

    nav_parts: list[str] = []
    if prev_file:
        nav_parts.append(f'<a href="{prev_file}">&#8592; Previous</a>')
    if next_file:
        nav_parts.append(f'<a href="{next_file}">Next &#8594;</a>')
    nav_html = ""
    if nav_parts:
        nav_html = f'<p class="index-page-nav">{" &nbsp;|&nbsp; ".join(nav_parts)}</p>'

    body = (
        f"<h1>{_e(category)}</h1>"
        f'<p class="section-index-intro">{intro}</p>'
        f'<div class="section-index">{_section_index_entries_html(page_articles, slug, start_num)}</div>'
        f"{nav_html}"
    )
    page_title = f"{category} — Contents" if total_pages == 1 else f"{category} — Contents ({page_num}/{total_pages})"
    return _xhtml_wrap(page_title, body)


def _article_xhtml(category: str, art: dict, index: int, total: int) -> bytes:
    pub_tag = f" &middot; {art['published']}" if art.get("published") else ""
    body = (
        f'<header class="article-header">'
        f'<p class="article-section">{_e(category)} &middot; {index} of {total}</p>'
        f'<h1 class="article-title">{_e(art["title"])}</h1>'
        f'<p class="meta">{_e(art["source"])}{pub_tag}</p>'
        f"</header>"
        f"{_article_body_html(art)}"
        f'<p class="read-more"><a href="{art["url"]}">Read full article online &#8594;</a></p>'
    )
    return _xhtml_wrap(art["title"], body)


def generate_epub(
    sections: dict[str, list[dict]],
    section_covers: dict[str, dict],
    global_cover: dict,
    output_path: Path,
) -> None:
    book = epub.EpubBook()
    now  = datetime.now()

    book.set_identifier(f"bitesize-{now.strftime('%Y%m%d%H%M%S')}")
    book.set_title(f"News Digest – {now.strftime('%B %d, %Y %H:%M')}")
    book.set_language("en")
    book.add_author("BiteSIze")

    css_item = epub.EpubItem(
        uid="style", file_name="style.css",
        media_type="text/css", content=_CSS,
    )
    book.add_item(css_item)

    cover_ch = epub.EpubHtml(title="News Digest", file_name="cover.xhtml", lang="en")
    cover_ch.content = _global_cover_xhtml(global_cover, sections, now)
    cover_ch.add_item(css_item)
    book.add_item(cover_ch)

    # Cover first: if `nav` is linear, Kindle opens the NCX link tree (unreadable).
    # Keep the nav document for the TOC button, but mark it non-linear in the spine.
    spine: list = [cover_ch, ("nav", "no")]
    toc: list = []

    for category, articles in sections.items():
        if not articles:
            continue

        slug = _slugify(category)
        section_links: list = []

        sec_cover_ch = epub.EpubHtml(
            title=f"{category} — Cover",
            file_name=f"cover_{slug}.xhtml",
            lang="en",
        )
        sec_cover_ch.content = _section_cover_xhtml(
            category, section_covers.get(category, {}), articles
        )
        sec_cover_ch.add_item(css_item)
        book.add_item(sec_cover_ch)
        spine.append(sec_cover_ch)

        page_size = INDEX_ENTRIES_PER_PAGE
        total_pages = max(1, (len(articles) + page_size - 1) // page_size)
        index_files: list[str] = []

        for page_num in range(1, total_pages + 1):
            start_idx = (page_num - 1) * page_size
            page_articles = articles[start_idx : start_idx + page_size]
            start_num = start_idx + 1
            file_name = _index_page_filename(slug, page_num)
            index_files.append(file_name)

            prev_file = index_files[-2] if page_num > 1 else None
            next_file = (
                _index_page_filename(slug, page_num + 1)
                if page_num < total_pages
                else None
            )

            index_ch = epub.EpubHtml(
                title=f"{category} — Contents"
                if total_pages == 1
                else f"{category} — Contents ({page_num}/{total_pages})",
                file_name=file_name,
                lang="en",
            )
            index_ch.content = _section_index_page_xhtml(
                category,
                page_articles,
                slug,
                start_num,
                len(articles),
                page_num,
                total_pages,
                prev_file,
                next_file,
            )
            index_ch.add_item(css_item)
            book.add_item(index_ch)
            spine.append(index_ch)

        section_links.append(
            epub.Link(index_files[0], "Contents", f"index_{slug}")
        )
        for page_num in range(2, total_pages + 1):
            section_links.append(
                epub.Link(
                    index_files[page_num - 1],
                    f"Contents ({page_num}/{total_pages})",
                    f"index_{slug}_{page_num:02d}",
                )
            )

        total = len(articles)
        for i, art in enumerate(articles, start=1):
            art_slug = f"{slug}_{i:02d}"
            art_ch = epub.EpubHtml(
                title=art["title"],
                file_name=f"article_{art_slug}.xhtml",
                lang="en",
            )
            art_ch.content = _article_xhtml(category, art, i, total)
            art_ch.add_item(css_item)
            book.add_item(art_ch)
            spine.append(art_ch)
            section_links.append(
                epub.Link(f"article_{art_slug}.xhtml", art["title"], f"art_{art_slug}")
            )

        toc.append((epub.Section(category), tuple(section_links)))

    book.toc   = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    OUTPUT_DIR.mkdir(exist_ok=True)
    epub.write_epub(str(output_path), book)
