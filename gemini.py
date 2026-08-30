import json
import re
from typing import Optional

from ai_locale import ai_output_language_rule
from config import console, get_settings
from ai import call as _call_ai, available as _ai_available

CLUSTERED_AI_SCORE_RATIO = 0.35
LISTWISE_SCORE_HIGH = 92
LISTWISE_SCORE_LOW = 40


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


def relevance_display(art: dict) -> str:
    """Format internal 0–100 score as a 0–10 rating (one decimal)."""
    return f"{article_relevance(art) / 10:.1f}"


def _normalize_relevance(raw) -> int:
    """Coerce model output to 0–100 for sorting and EPUB display."""
    try:
        v = int(round(float(raw)))
    except (TypeError, ValueError):
        return 50
    return max(0, min(100, v))


def _fallback_relevance(art: dict) -> int:
    """Weak stand-in when the model omits a score.

    Length is not importance. Keep the value below 70 so fallbacks cannot
    occupy the top of the book, and use a continuous map so long articles
    do not all land on 78 / 70 / 62.
    """
    body = (art.get("content") or "").strip()
    n = len(body)
    if n <= 0:
        return 30
    return 30 + min(28, n * 28 // 8000)


def _relevance_from_listwise_rank(rank: int, n: int) -> int:
    """Map 1-based listwise rank (1 = most important) to 0–100."""
    if n <= 0:
        return 50
    if n == 1:
        return LISTWISE_SCORE_HIGH
    span = LISTWISE_SCORE_HIGH - LISTWISE_SCORE_LOW
    return LISTWISE_SCORE_HIGH - (rank - 1) * span // (n - 1)


def _assign_fallback_relevance(art: dict) -> None:
    art["relevance"] = _fallback_relevance(art)
    art["relevance_source"] = "fallback"


def _ai_scores_too_clustered(ai_articles: list[dict]) -> bool:
    n = len(ai_articles)
    if n < 2:
        return False
    unique = len({a["relevance"] for a in ai_articles})
    return unique / n < CLUSTERED_AI_SCORE_RATIO


def _listwise_rank_instruction(n: int) -> str:
    return (
        f"You are a news editor. Rank these {n} story titles by importance to a general reader "
        "(impact, timeliness, breadth). "
        "Return ONLY a raw JSON array — no markdown fences — ordered most important first: "
        '[{"id":0},{"id":2},{"id":1}] '
        "Each object needs only id matching the bracketed index before each title."
        + ai_output_language_rule()
    )


def _parse_listwise_order(response: str, n: int) -> list[int] | None:
    parsed = _extract_json(response, label="listwise-rank")
    if not isinstance(parsed, list):
        return None
    order: list[int] = []
    seen: set[int] = set()
    for item in parsed:
        if isinstance(item, dict):
            idx = item.get("id")
        else:
            try:
                idx = int(item)
            except (TypeError, ValueError):
                continue
        if not isinstance(idx, int) or not (0 <= idx < n) or idx in seen:
            continue
        seen.add(idx)
        order.append(idx)
    if len(order) != n:
        return None
    return order


def _maybe_remap_clustered_batch(batch_results: list[dict]) -> None:
    """One listwise pass when AI scores in a batch are too clustered."""
    ai_articles = [a for a in batch_results if a.get("relevance_source") == "ai"]
    if not _ai_scores_too_clustered(ai_articles):
        return

    n = len(ai_articles)
    title_block = ""
    for local_i, art in enumerate(ai_articles):
        title_block += f'[{local_i}] "{art["title"]}"\n'

    response = _call_ai(_listwise_rank_instruction(n), title_block, label="listwise-rank")
    if not response:
        return
    order = _parse_listwise_order(response, n)
    if order is None:
        return

    for rank, local_i in enumerate(order, start=1):
        ai_articles[local_i]["relevance"] = _relevance_from_listwise_rank(rank, n)


def spread_tied_scores(articles: list[dict]) -> list[dict]:
    """Give unique scores inside a tied group, newest first, without reordering groups."""
    from collections import defaultdict

    groups: dict[int, list[int]] = defaultdict(list)
    for i, art in enumerate(articles):
        groups[article_relevance(art)].append(i)

    unique_scores = sorted(groups.keys(), reverse=True)
    for idx, score in enumerate(unique_scores):
        members = groups[score]
        if len(members) < 2:
            continue
        next_score = unique_scores[idx + 1] if idx + 1 < len(unique_scores) else None
        floor = (next_score + 1) if next_score is not None else max(0, score - len(members) + 1)
        room = max(1, score - floor + 1)
        members_sorted = sorted(
            members,
            key=lambda i: (
                -int(articles[i].get("published_ts") or 0),
                (articles[i].get("title") or "").lower(),
            ),
        )
        n = len(members_sorted)
        for rank, i in enumerate(members_sorted):
            if room >= n:
                articles[i]["relevance"] = score - rank
            else:
                step = (room - 1) / max(n - 1, 1)
                articles[i]["relevance"] = score - int(round(rank * step))
    return articles


def process_articles(articles: list[dict], batch_size: int | None = None) -> list[dict]:
    """
    Single flat pass over all articles.

    Each batch of `batch_size` articles is sent in ONE call that simultaneously:
      • Filters out ads / sponsored content  (skip=true)  → logged to console
      • Writes a 2-sentence factual summary   (summary="…")
      • Assigns relevance (0–100) for ranking the digest

    Falls back gracefully: if Gemini is unavailable or a batch fails,
    the original articles are kept without summaries.
    """
    if batch_size is None:
        batch_size = get_settings().gemini_batch_size
    if not _ai_available():
        console.print("  [yellow]⚠  AI backend not available — skipping AI processing[/yellow]")
        out = []
        for art in articles:
            a = art.copy()
            _assign_fallback_relevance(a)
            out.append(a)
        return spread_tied_scores(out)

    processed: list[dict] = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        batch_results: list[dict] = []

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
            "relevance: integer 0–100 comparing this story to the others in THIS batch "
            "(impact, timeliness, breadth of audience, central vs niche). "
            "Use the full scale: at most one in five items above 80, at least one in five below 45. "
            "Do not give several stories the same number."
            + ai_output_language_rule()
        )

        response = _call_ai(instruction, article_block)

        if response:
            parsed = _extract_json(response)
            if isinstance(parsed, list):
                handled: set[int] = set()
                for item in parsed:
                    idx = item.get("id", -1)
                    if not (0 <= idx < len(batch)):
                        continue
                    handled.add(idx)
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
                            art["relevance_source"] = "ai"
                        else:
                            _assign_fallback_relevance(art)
                        batch_results.append(art)
                for j, art in enumerate(batch):
                    if j in handled:
                        continue
                    a = art.copy()
                    _assign_fallback_relevance(a)
                    batch_results.append(a)
                _maybe_remap_clustered_batch(batch_results)
                processed.extend(batch_results)
                continue  # batch handled

        # Fallback: keep all articles without summaries (score heuristically for ordering)
        for art in batch:
            a = art.copy()
            if "relevance" not in a:
                _assign_fallback_relevance(a)
            else:
                a["relevance_source"] = "fallback"
            processed.append(a)

    return spread_tied_scores(processed)


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
        + ai_output_language_rule()
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
        + ai_output_language_rule()
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


def _truncate_text(text: str, max_chars: int | None = None) -> str:
    if max_chars is None:
        max_chars = get_settings().truncate_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"
