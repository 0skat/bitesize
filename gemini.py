import json
import re
from typing import Optional

from ai_locale import ai_output_language_rule, ai_summary_language_rule
from config import console, get_settings
from ai import call as _call_ai, available as _ai_available
from tags import TEMAS, normalize_tags

CLUSTERED_AI_SCORE_RATIO = 0.35


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


def _relevance_from_listwise_rank(rank: int, n: int, *, high: int, low: int) -> int:
    """Map 1-based listwise rank (1 = most important) across a score span."""
    if n <= 0:
        return 50
    if n == 1:
        return high
    span = high - low
    return high - (rank - 1) * span // (n - 1)


def _listwise_remap_bounds(ai_articles: list[dict]) -> tuple[int, int]:
    """Score span for listwise remap: batch min/max, spread downward when tied."""
    scores = [a["relevance"] for a in ai_articles]
    high = max(scores)
    low = min(scores)
    n = len(ai_articles)
    if n > 1 and high == low:
        low = max(0, high - (n - 1))
    return high, low


def _listwise_cluster_log_line(
    ai_articles: list[dict],
    *,
    order: list[int] | None,
    empty_response: bool = False,
) -> str:
    """One-line status for clustered listwise pass (testable without Rich)."""
    n = len(ai_articles)
    unique = len({a["relevance"] for a in ai_articles})
    ratio = unique / n if n else 0.0
    ratio_text = f"ratio={ratio:.2f}"
    if empty_response:
        return f"listwise skipped-empty {ratio_text}"
    if order is None:
        return f"listwise skipped-invalid {ratio_text}"
    return f"listwise fired {ratio_text}"


def user_interests() -> str:
    """Free-text description of what the reader wants, or "" when unset."""
    return (get_settings().user_interests or "").strip()


def _relevance_rule() -> str:
    """Scoring instruction: generic newsworthiness, or fit to the reader.

    Without interests this is the upstream batch-relative rule. With interests
    the score becomes absolute — fit to this reader, judged per story — because
    a keep threshold only means something if 70 means the same thing in every
    batch. The forced spread is dropped for the same reason: a batch of twenty
    stories the reader does not care about should be allowed to score low across
    the board.
    """
    interests = user_interests()
    if not interests:
        return (
            "relevance: integer 0–100 comparing this story to the others in THIS batch "
            "(impact, timeliness, breadth of audience, central vs niche). "
            "Use the full scale: at most one in five items above 80, at least one in five below 45. "
            "Do not give several stories the same number. "
        )
    return (
        "relevance: integer 0–100 scoring how much THIS READER would want to read the story. "
        f"The reader describes their interests as: {interests!r}. "
        "Judge each story on its own against those interests — do NOT grade on a curve "
        "against the other stories in this batch, and do not force a spread. "
        "Scoring guide: 85–100 squarely in their interests; 60–84 adjacent or useful context; "
        "30–59 general news they did not ask for; 0–29 off-topic. "
        "A major world event outside their stated interests belongs below 60. "
        "A niche story inside them belongs above 85. "
        "Use general news impact only to break ties between equally relevant stories. "
    )


# Titles are short, so the screening pass can take far larger batches than the
# summarising pass. Each batch is one AI call.
PREFILTER_BATCH_SIZE = 60

# Score given to an article whose screening batch failed to come back. Neutral
# rather than zero: a failed call must not silently delete its articles, but it
# should not let them outrank genuinely-matched ones either.
PREFILTER_NEUTRAL_SCORE = 50


def _prefilter_instruction(n: int, interests: str) -> str:
    return (
        f"You are screening {n} news headlines for one reader. "
        f"The reader describes their interests as: {interests!r}. "
        "Return ONLY a raw JSON array — no markdown fences, no explanation — "
        'one object per headline: [{"id":0,"score":85}] '
        "score: integer 0–100 for how much this reader would want to read the "
        "story, judged from the headline alone. Be decisive: clearly inside "
        "their interests above 70, clearly outside below 30. This is a cheap "
        "screening pass before the real read, so when a headline is ambiguous "
        "score it in the middle rather than rejecting it. "
        "Every id from 0 to " + str(n - 1) + " must appear exactly once."
    )


def _parse_prefilter_scores(response: str, n: int, label: str) -> dict[int, int]:
    parsed = _extract_json(response, label=label)
    if not isinstance(parsed, list):
        return {}
    out: dict[int, int] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        idx = item.get("id", -1)
        if not isinstance(idx, int) or not (0 <= idx < n):
            continue
        out[idx] = _normalize_relevance(item.get("score"))
    return out


def prefilter_by_title(
    articles: list[dict], keep: int
) -> tuple[list[dict], list[dict]]:
    """Screen on titles alone, keeping the `keep` best matches.

    The full pass fetches and summarises every article before anything is
    filtered, so a large feed list pays to summarise stories the keep-list then
    throws away. Titles are cheap: one call screens sixty of them, and only the
    survivors get a body fetch and a summary.

    Returns (kept, dropped). Fails open — no interests, no AI, or nothing to
    gain and everything is kept, because dropping an article here means it is
    never read at all.
    """
    interests = user_interests()
    if keep <= 0 or not interests or len(articles) <= keep:
        return articles, []
    if not _ai_available():
        console.print(
            "  [yellow]⚠  AI backend not available — skipping title screen[/yellow]"
        )
        return articles, []

    batch_size = max(1, get_settings().prefilter_batch_size)
    scores: dict[int, int] = {}
    for start in range(0, len(articles), batch_size):
        batch = articles[start : start + batch_size]
        label = f"prefilter-{start // batch_size + 1}"
        title_block = "".join(
            f'[{i}] "{art.get("title", "")}"\n' for i, art in enumerate(batch)
        )
        response = _call_ai(
            _prefilter_instruction(len(batch), interests), title_block, label=label
        )
        batch_scores = _parse_prefilter_scores(response, len(batch), label) if response else {}
        if not batch_scores:
            console.print(
                f"  [yellow]⚠  [{label}] no usable scores — "
                f"{len(batch)} titles held at neutral[/yellow]"
            )
        for i, art in enumerate(batch):
            scores[start + i] = batch_scores.get(i, PREFILTER_NEUTRAL_SCORE)

    for i, art in enumerate(articles):
        art["prefilter_score"] = scores.get(i, PREFILTER_NEUTRAL_SCORE)

    # Scores bunch up — a screening model asked to judge a bare headline returns
    # the same number for dozens of them — so the cut line usually falls inside
    # a tie. Breaking that tie by list order would hand every slot to whichever
    # feeds happen to come first, burying whole interest areas. Rank each
    # article within its own section first, then interleave: at equal scores the
    # best of every section is taken before the second-best of any.
    rank_in_section: dict[int, int] = {}
    by_section: dict[str, list[int]] = {}
    for i, art in enumerate(articles):
        by_section.setdefault(art.get("category", ""), []).append(i)
    for members in by_section.values():
        members.sort(key=lambda i: (-scores.get(i, PREFILTER_NEUTRAL_SCORE), i))
        for position, i in enumerate(members):
            rank_in_section[i] = position

    ranked = sorted(
        range(len(articles)),
        key=lambda i: (
            -scores.get(i, PREFILTER_NEUTRAL_SCORE),
            rank_in_section[i],
            i,
        ),
    )
    keep_idx = set(ranked[:keep])
    kept = [art for i, art in enumerate(articles) if i in keep_idx]
    dropped = [art for i, art in enumerate(articles) if i not in keep_idx]
    return kept, dropped


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
    # With interests set, scores are absolute and clustering is real signal —
    # re-spreading would lift off-topic stories back over min_keep_score.
    if user_interests():
        return

    ai_articles = [a for a in batch_results if a.get("relevance_source") == "ai"]
    if not _ai_scores_too_clustered(ai_articles):
        return

    n = len(ai_articles)
    title_block = ""
    for local_i, art in enumerate(ai_articles):
        title_block += f'[{local_i}] "{art["title"]}"\n'

    response = _call_ai(_listwise_rank_instruction(n), title_block, label="listwise-rank")
    if not response:
        console.print(f"  [dim]{_listwise_cluster_log_line(ai_articles, order=None, empty_response=True)}[/dim]")
        return
    order = _parse_listwise_order(response, n)
    if order is None:
        console.print(f"  [dim]{_listwise_cluster_log_line(ai_articles, order=None)}[/dim]")
        return

    high, low = _listwise_remap_bounds(ai_articles)
    for rank, local_i in enumerate(order, start=1):
        ai_articles[local_i]["relevance"] = _relevance_from_listwise_rank(
            rank, n, high=high, low=low,
        )
    console.print(f"  [dim]{_listwise_cluster_log_line(ai_articles, order=order)}[/dim]")


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
            normalize_tags(a)
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

        temas_list = ", ".join(sorted(TEMAS))
        instruction = (
            f"You are a news editor reviewing {len(batch)} article snippets. "
            "Return ONLY a raw JSON array — no markdown fences, no explanation — with one object per article: "
            '[{"id":0,"skip":false,"summary":"Sentence one. Sentence two.","relevance":72,'
            '"tipo":"artigo-completo","temas":["política"]}] '
            "Rules: skip=true ONLY for pure advertisements or sponsored/promotional content; "
            "real news is never skipped regardless of topic. "
            "summary: exactly 2 factual sentences, no editorialising, no filler phrases. "
            + _relevance_rule() +
            'tipo: exactly "resumo" (paywall teaser or lede-only) or "artigo-completo" (enough body to read). '
            f"temas: zero or more from this fixed list only — do not invent labels: {temas_list}."
            + ai_summary_language_rule()
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
                        normalize_tags(art, item)
                        batch_results.append(art)
                for j, art in enumerate(batch):
                    if j in handled:
                        continue
                    a = art.copy()
                    _assign_fallback_relevance(a)
                    normalize_tags(a)
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
            normalize_tags(a)
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
    if not get_settings().ai_covers_enabled:
        return {}

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
    if not get_settings().ai_covers_enabled:
        return {}

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
