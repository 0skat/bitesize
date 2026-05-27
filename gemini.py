import json
import re
from typing import Optional

from config import console, GEMINI_BATCH_SIZE, MIN_BODY_CHARS, TRUNCATE_CHARS
from ai import call as _call_ai, available as _ai_available


def _extract_json(response: str, label: str = ""):
    """Try to parse JSON from a Gemini response, tolerating markdown fences."""
    tag = f"[{label}] " if label else ""
    # Direct parse
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass
    # Try extracting a JSON array first, then an object (separate greedy patterns)
    for pattern in (r'\[[\s\S]*\]', r'\{[\s\S]*\}'):
        match = re.search(pattern, response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    console.print(
        f"  [yellow]⚠  {tag}Could not extract JSON from response "
        f"(first 200 chars): {response[:200]!r}[/yellow]"
    )
    return None


def article_relevance(art: dict) -> int:
    """Return 0–100 score for sorting; missing values use heuristic fallback."""
    if "relevance" in art and art["relevance"] is not None:
        return _normalize_relevance(art["relevance"])
    return _fallback_relevance(art)


def _normalize_relevance(raw) -> int:
    """Coerce model output to 0–100 for sorting and EPUB display."""
    try:
        v = int(round(float(raw)))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, v))


def _fallback_relevance(art: dict) -> int:
    """When the model omits a score, prefer longer readable extracts."""
    body = (art.get("content") or "").strip()
    n = len(body)
    if n >= 3500:
        return 78
    if n >= 2000:
        return 70
    if n >= MIN_BODY_CHARS:
        return 62
    if n > 120:
        return 48
    return 40


def process_articles(articles: list[dict], batch_size: int = GEMINI_BATCH_SIZE) -> list[dict]:
    """
    Single flat pass over all articles.

    Each batch of `batch_size` articles is sent in ONE call that simultaneously:
      • Filters out ads / sponsored content  (skip=true)  → logged to console
      • Writes a 2-sentence factual summary   (summary="…")
      • Assigns relevance (0–100) for ranking the digest

    Falls back gracefully: if Gemini is unavailable or a batch fails,
    the original articles are kept without summaries.
    """
    if not _ai_available():
        console.print("  [yellow]⚠  AI backend not available — skipping AI processing[/yellow]")
        out = []
        for art in articles:
            a = art.copy()
            a["relevance"] = _fallback_relevance(a)
            out.append(a)
        return out

    processed: list[dict] = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]

        article_block = ""
        for j, art in enumerate(batch):
            preview = (
                _truncate_text(art["content"]) if art["content"] else art["title"]
            )
            article_block += f'[{j}] "{art["title"]}"\n{preview}\n\n'

        instruction = (
            f"You are a news editor reviewing {len(batch)} article snippets. "
            "Return ONLY a raw JSON array — no markdown fences, no explanation — with one object per article: "
            '[{"id":0,"skip":false,"summary":"Sentence one. Sentence two.","relevance":72}] '
            "Rules: skip=true ONLY for pure advertisements or sponsored/promotional content; "
            "real news is never skipped regardless of topic. "
            "summary: exactly 2 factual sentences, no editorialising, no filler phrases. "
            "relevance: integer 0–100 for how important this story is to a well-informed reader today "
            "(consider impact, timeliness, breadth of audience, and how central the topic is vs niche); "
            "use the full scale — not every item should be 80+."
        )

        response = _call_ai(instruction, article_block)

        if response:
            parsed = _extract_json(response)
            if isinstance(parsed, list):
                for item in parsed:
                    idx = item.get("id", -1)
                    if not (0 <= idx < len(batch)):
                        continue
                    if item.get("skip", False):
                        art = batch[idx]
                        console.print(
                            f"  [dim]✗  filtered:[/dim] \"{art['title']}\" "
                            f"[dim]({art['source']})[/dim]"
                        )
                    else:
                        art = batch[idx].copy()
                        art["summary"] = item.get("summary", "")
                        if "relevance" in item:
                            art["relevance"] = _normalize_relevance(item.get("relevance"))
                        else:
                            art["relevance"] = _fallback_relevance(art)
                        processed.append(art)
                continue  # batch handled

        # Fallback: keep all articles without summaries (score heuristically for ordering)
        for art in batch:
            a = art.copy()
            if "relevance" not in a:
                a["relevance"] = _fallback_relevance(a)
            processed.append(a)

    return processed


def generate_section_cover(category: str, articles: list[dict]) -> dict:
    """
    Generate a newspaper-style editorial cover for one category.

    Returns a dict:
      { "headline": str, "editorial": str,
        "top_stories": [{"title": str, "one_liner": str}, ...] }
    Falls back to {} on any failure.
    """
    label = f"section-cover:{category}"

    if not _ai_available():
        console.print(f"  [yellow]⚠  [{label}] AI backend unavailable[/yellow]")
        return {}
    if not articles:
        console.print(f"  [yellow]⚠  [{label}] No articles to summarise[/yellow]")
        return {}

    article_block = "\n".join(
        f"[{i}] {art['title']}: {art['summary'] or art['title']}"
        for i, art in enumerate(articles[:20])
    )

    instruction = (
        f"You are a newspaper editor for the {category} section. "
        f"Based on these {min(len(articles), 20)} articles, write a newspaper-style section front page. "
        "Return ONLY a raw JSON object — no markdown fences, no explanation: "
        '{"headline":"...","editorial":"...","top_stories":[{"title":"...","one_liner":"..."}]} '
        "Rules: "
        "headline: short punchy headline summarising today's biggest story (max 12 words); "
        "editorial: 2-3 sentences newspaper-style overview of today's top stories in this section; "
        "top_stories: exactly 3 items, each with the original article title and a concise one-liner."
    )

    response = _call_ai(instruction, article_block, label=label)
    if not response:
        console.print(f"  [yellow]⚠  [{label}] No response from AI[/yellow]")
        return {}

    parsed = _extract_json(response, label=label)
    if not isinstance(parsed, dict):
        console.print(f"  [yellow]⚠  [{label}] Expected dict, got {type(parsed).__name__}[/yellow]")
        return {}
    if "headline" not in parsed:
        console.print(f"  [yellow]⚠  [{label}] Missing 'headline' key — keys: {list(parsed.keys())}[/yellow]")
        return {}

    return parsed


def generate_global_cover(section_covers: dict[str, dict]) -> dict:
    """
    Generate the overall EPUB front page from per-section cover data.

    Returns a dict:
      { "headline": str, "editorial": str,
        "highlights": [{"section": str, "headline": str, "story": str}, ...] }
    Falls back to {} on any failure.
    """
    label = "global-cover"

    if not _ai_available():
        console.print(f"  [yellow]⚠  [{label}] AI backend unavailable[/yellow]")
        return {}
    if not section_covers:
        console.print(f"  [yellow]⚠  [{label}] No section covers to work from[/yellow]")
        return {}

    block = "\n\n".join(
        f"[{section}]\n"
        f"Headline: {data.get('headline', '')}\n"
        f"Editorial: {data.get('editorial', '')}"
        for section, data in section_covers.items()
        if data
    )
    if not block:
        console.print(f"  [yellow]⚠  [{label}] All section covers are empty[/yellow]")
        return {}

    instruction = (
        "You are an editor-in-chief of a newspaper. "
        "Based on these section summaries, write today's front page. "
        "Return ONLY a raw JSON object — no markdown fences, no explanation: "
        '{"headline":"...","editorial":"...","highlights":['
        '{"section":"...","headline":"...","story":"..."}, ...]} '
        "Rules: "
        "headline: today's single most important headline across all sections (max 12 words); "
        "editorial: 2-3 sentences on the day's most significant news overall; "
        "highlights: one object per section; "
        "each highlight must include section (category name), "
        "headline (the lead article title or a tight rewrite, max 14 words), "
        "and story (one sentence expanding the angle for a newspaper reader)."
    )

    response = _call_ai(instruction, block, label=label)
    if not response:
        console.print(f"  [yellow]⚠  [{label}] No response from AI[/yellow]")
        return {}

    parsed = _extract_json(response, label=label)
    if not isinstance(parsed, dict):
        console.print(f"  [yellow]⚠  [{label}] Expected dict, got {type(parsed).__name__}[/yellow]")
        return {}
    if "headline" not in parsed:
        console.print(f"  [yellow]⚠  [{label}] Missing 'headline' key — keys: {list(parsed.keys())}[/yellow]")
        return {}

    return parsed


def _truncate_text(text: str, max_chars: int = TRUNCATE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"
