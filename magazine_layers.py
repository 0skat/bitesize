"""Magazine-style editorial layers — avoid repeating the cover story."""

from __future__ import annotations

import re

from gemini import article_relevance


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_same_story(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    url_a = (a.get("url") or "").strip()
    url_b = (b.get("url") or "").strip()
    if url_a and url_b and url_a == url_b:
        return True
    title_a = _norm(a.get("title"))
    title_b = _norm(b.get("title"))
    if not title_a or not title_b:
        return False
    if title_a == title_b:
        return True
    if len(title_a) > 24 and (title_a in title_b or title_b in title_a):
        return True
    return False


def headline_matches(a: dict | None, headline: str) -> bool:
    if not a or not headline:
        return False
    return is_same_story(a, {"title": headline, "url": ""})


def _cover_sort_key(relevance: int, cat: str, art: dict) -> tuple:
    """Prefer AI-scored articles for cover picks; then relevance; then section/title."""
    ai_first = 0 if art.get("relevance_source") == "ai" else 1
    return (ai_first, -relevance, (cat or "").lower(), _norm(art.get("title")))


def article_rank_sort_key(art: dict) -> tuple:
    """Shared sort key for section order and cover picks."""
    return _cover_sort_key(article_relevance(art), "", art)


def find_hero_article(
    sections: dict[str, list[dict]],
    global_cover: dict | None,
) -> tuple[dict | None, str | None]:
    """Edition hero: the single cover-line story (highest relevance by default)."""
    headline = ((global_cover or {}).get("headline") or "").strip()

    if headline:
        for cat, arts in sections.items():
            for art in arts or []:
                if headline_matches(art, headline):
                    return art, cat

    ranked: list[tuple[int, str, dict]] = []
    for cat, arts in sections.items():
        for art in arts or []:
            ranked.append((article_relevance(art), cat, art))
    if not ranked:
        return None, None
    ranked.sort(
        key=lambda x: _cover_sort_key(x[0], x[1], x[2]),
    )
    _, cat, art = ranked[0]
    return art, cat


def lead_for_section(articles: list[dict], hero: dict | None) -> dict | None:
    """Section-front lead: top story in this desk that is not the edition hero."""
    for art in sorted(articles or [], key=article_rank_sort_key):
        if hero and is_same_story(art, hero):
            continue
        return art
    return articles[0] if articles else None


def cover_teasers(
    sections: dict[str, list[dict]],
    hero: dict | None,
    limit: int = 3,
) -> list[str]:
    """
    Cover rails — one inside teaser per section (never the hero).

    Like magazine cover lines: "Plus: Tech · The Verge · …"
    """
    teasers: list[str] = []
    for cat, arts in sections.items():
        lead = lead_for_section(arts, hero)
        if not lead or (hero and is_same_story(lead, hero)):
            continue
        source = (lead.get("source") or "").strip()
        title = (lead.get("title") or "").strip()
        if source:
            teasers.append(f"{cat} · {source} · {title}")
        else:
            teasers.append(f"{cat} · {title}")
    return teasers[:limit]


def section_desk_highlights(
    sections: dict[str, list[dict]],
    hero: dict | None,
) -> list[dict]:
    """Opening-spread desk notes — one distinct lead per section."""
    out: list[dict] = []
    for cat, arts in sections.items():
        lead = lead_for_section(arts, hero)
        if not lead:
            continue
        out.append({
            "section": cat,
            "headline": lead.get("title", ""),
            "story": (lead.get("summary") or lead.get("title") or "").strip(),
            "source": lead.get("source", ""),
        })
    return out


def ranked_excluding_hero(
    sections: dict[str, list[dict]],
    hero: dict | None,
    limit: int,
) -> list[tuple[int, str, dict]]:
    ranked: list[tuple[int, str, dict]] = []
    for cat, arts in sections.items():
        for art in arts or []:
            if hero and is_same_story(art, hero):
                continue
            ranked.append((article_relevance(art), cat, art))
    ranked.sort(
        key=lambda x: _cover_sort_key(x[0], x[1], x[2]),
    )
    return ranked[:limit]
