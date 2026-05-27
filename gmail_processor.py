"""AI triage and summarisation of Gmail threads for the digest."""
import json
import re
from typing import Optional

from config import console
from ai import call as _call_ai, available as _ai_available

_GMAIL_BATCH_SIZE = 10
_CONTENT_MAX_CHARS = 800

_PRIORITY_ORDER = {"action": 0, "update": 1, "fyi": 2}


def _extract_json(response: str, label: str = ""):
    """Try to parse JSON from a Gemini response, tolerating markdown fences."""
    tag = f"[{label}] " if label else ""
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass
    for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
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


# ── Public API ────────────────────────────────────────────────────────────────


def process_email_threads(threads: list[dict]) -> list[dict]:
    """
    AI triage and summarisation of Gmail threads.

    Calls Gemini in batches of 10. Skips automated/marketing threads.
    Returns article dicts sorted by priority: action → update → fyi.
    """
    if not _ai_available():
        console.print(
            "  [yellow]⚠  Gemini CLI not found — returning threads without AI triage[/yellow]"
        )
        return _threads_to_articles(threads, summaries={})

    triage_results: dict[int, dict] = {}

    for batch_start in range(0, len(threads), _GMAIL_BATCH_SIZE):
        batch = threads[batch_start : batch_start + _GMAIL_BATCH_SIZE]
        batch_results = _triage_batch(batch, offset=batch_start)
        triage_results.update(batch_results)

    articles = _build_articles(threads, triage_results)
    return sorted(articles, key=lambda a: _PRIORITY_ORDER.get(a.get("priority", "fyi"), 2))


def generate_inbox_cover(articles: list[dict]) -> dict:
    """
    Generate a newspaper-style cover for the Inbox section.

    Returns {"headline": str, "editorial": str, "top_stories": [...]}
    Falls back to {} on any failure.
    """
    label = "section-cover:Inbox"

    if not _ai_available():
        console.print(f"  [yellow]⚠  [{label}] Gemini unavailable[/yellow]")
        return {}
    if not articles:
        console.print(f"  [yellow]⚠  [{label}] No articles to summarise[/yellow]")
        return {}

    article_block = "\n".join(
        f"[{i}] {art['title']} ({art.get('priority', 'fyi')}): {art.get('summary') or art['title']}"
        for i, art in enumerate(articles[:20])
    )

    instruction = (
        "You are a personal assistant writing a one-page inbox briefing for a Kindle digest. "
        "Based on these summarized email threads, write an inbox overview. "
        "Return ONLY a raw JSON object — no markdown fences: "
        '{"headline":"...","editorial":"...","top_stories":[{"title":"...","one_liner":"..."}]} '
        "Rules: "
        "headline: the single most important thing in the inbox today (max 12 words, no fluff). "
        'Good: "3 decisions needed before EOD, 1 from leadership". '
        'Bad: "Your inbox summary for today". '
        "editorial: 2 sentences. First: overall inbox health (busy/quiet, action-heavy/informational). "
        "Second: the most important thread in one sentence. "
        "top_stories: exactly 3 items, priority 'action' threads first, then 'update'. "
        "title: the thread subject. one_liner: the summary sentence from triage."
    )

    response = _call_ai(instruction, article_block, label=label)
    if not response:
        console.print(f"  [yellow]⚠  [{label}] No response from Gemini[/yellow]")
        return {}

    parsed = _extract_json(response, label=label)
    if not isinstance(parsed, dict):
        console.print(
            f"  [yellow]⚠  [{label}] Expected dict, got {type(parsed).__name__}[/yellow]"
        )
        return {}
    if "headline" not in parsed:
        console.print(
            f"  [yellow]⚠  [{label}] Missing 'headline' key — keys: {list(parsed.keys())}[/yellow]"
        )
        return {}

    return parsed


# ── Internal helpers ──────────────────────────────────────────────────────────


def _triage_batch(batch: list[dict], offset: int) -> dict[int, dict]:
    """
    Send one batch to Gemini for triage + summarisation.
    Returns {absolute_index: {"skip": bool, "priority": str, "summary": str}}.
    """
    thread_block = ""
    for j, thread in enumerate(batch):
        thread_block += (
            f'[{j}] Subject: "{thread["subject"]}" | From: {thread["sender"]}\n'
            f'{thread["body"][:500]}\n\n'
        )

    instruction = (
        "You are a personal assistant reviewing email threads for a busy professional "
        "reading a morning digest on their Kindle. They cannot act on emails right now — "
        "this is for awareness only.\n\n"
        f"Review these {len(batch)} email threads and return ONLY a raw JSON array, "
        "one object per thread: "
        '[{"id":0,"skip":false,"priority":"action|update|fyi","summary":"..."}]\n\n'
        "Rules:\n"
        "- skip: true for automated notifications, receipts, marketing, newsletters, "
        "calendar invites with no context, and any thread with no human-written content\n"
        "- priority:\n"
        '    "action"  — someone is waiting for a response or decision (reply needed, approval, question)\n'
        '    "update"  — meaningful update from a real person (project status, news from a colleague)\n'
        '    "fyi"     — informational, no response needed\n'
        "- summary: one sentence maximum. Lead with WHO and WHAT.\n"
        '  Good: "Ana asked for feedback on the Q2 proposal by Friday."\n'
        '  Bad:  "This email is about a proposal from Ana regarding Q2."'
    )

    response = _call_ai(instruction, thread_block, label=f"gmail-triage:{offset}")
    if not response:
        return {}

    parsed = _extract_json(response, label=f"gmail-triage:{offset}")
    if not isinstance(parsed, list):
        return {}

    results: dict[int, dict] = {}
    for item in parsed:
        local_idx = item.get("id", -1)
        if not (0 <= local_idx < len(batch)):
            continue
        results[offset + local_idx] = {
            "skip": item.get("skip", False),
            "priority": item.get("priority", "fyi"),
            "summary": item.get("summary", ""),
        }
    return results


def _build_articles(threads: list[dict], triage: dict[int, dict]) -> list[dict]:
    """
    Combine original threads with triage results into article dicts.
    Threads not in triage (fallback) are included as 'fyi' with no summary.
    """
    articles: list[dict] = []
    for idx, thread in enumerate(threads):
        result = triage.get(idx, {})
        if result.get("skip", False):
            console.print(
                f'  [dim]✗  filtered:[/dim] "{thread["subject"]}" '
                f"[dim]({thread['sender']})[/dim]"
            )
            continue
        articles.append({
            "title": thread["subject"],
            "source": thread["sender"],
            "url": thread["url"],
            "published": thread["date"],
            "summary": result.get("summary", ""),
            "content": thread["body"][:_CONTENT_MAX_CHARS],
            "category": "Inbox",
            "priority": result.get("priority", "fyi"),
        })
    return articles


def _threads_to_articles(threads: list[dict], summaries: dict) -> list[dict]:
    """Fallback: convert threads to articles without AI triage."""
    return [
        {
            "title": t["subject"],
            "source": t["sender"],
            "url": t["url"],
            "published": t["date"],
            "summary": summaries.get(i, ""),
            "content": t["body"][:_CONTENT_MAX_CHARS],
            "category": "Inbox",
            "priority": "fyi",
        }
        for i, t in enumerate(threads)
    ]
