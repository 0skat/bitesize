"""Format calendar events with AI and convert to EPUB article dicts."""
import json
import re
from typing import Optional

from config import console
from ai import call as _call_ai, available as _ai_available

_CALENDAR_URL = "https://calendar.google.com"


def _extract_json(response: str, label: str = ""):
    tag = f"[{label}] " if label else ""
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass
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


# ── Main public functions ─────────────────────────────────────────────────────

def format_calendar_section(events: dict) -> list[dict]:
    """
    Convert raw calendar event dict into a list of synthetic article dicts
    for EPUB rendering. Makes one Gemini call for AI formatting, with a
    plain-text fallback if Gemini is unavailable.
    """
    if _ai_available():
        formatted = _format_with_gemini(events)
    else:
        formatted = None

    if formatted is None:
        formatted = _format_plain(events)

    return _build_articles(formatted, events)


def generate_calendar_cover(articles: list[dict]) -> dict:
    """
    Generate a day-at-a-glance section cover for the Calendar section.
    Returns {} on failure (epub.py handles missing covers gracefully).
    """
    label = "section-cover:Calendar"

    if not _ai_available():
        console.print(f"  [yellow]⚠  [{label}] Gemini unavailable[/yellow]")
        return {}
    if not articles:
        console.print(f"  [yellow]⚠  [{label}] No articles to summarise[/yellow]")
        return {}

    content_block = "\n\n".join(
        f"[{art['title']}]\n{art.get('content', '')}"
        for art in articles
    )

    instruction = (
        "You are a personal assistant writing a day-at-a-glance header for a Kindle digest. "
        "Return ONLY a raw JSON object — no markdown fences: "
        '{"headline":"...","editorial":"...","top_stories":[{"title":"...","one_liner":"..."}]} '
        "Rules: "
        "headline: characterize the day in max 10 words. "
        "Good: 'Heavy meeting day — 5 events, 2 need prep'. "
        "Good: 'Light day — one afternoon call'. "
        "Bad: 'Your calendar for today'. "
        "editorial: 2 sentences. First: today's rhythm (back-to-back vs. space to work, etc.). "
        "Second: the most important or time-sensitive event this week. "
        "top_stories: the 3 most significant events (today first, then this week). "
        "title: event name. one_liner: time + any key context."
    )

    response = _call_ai(instruction, content_block, label=label)
    if not response:
        return {}

    parsed = _extract_json(response, label=label)
    if not isinstance(parsed, dict) or "headline" not in parsed:
        return {}

    return parsed


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format_with_gemini(events: dict) -> Optional[dict]:
    instruction = (
        "You are a personal assistant preparing a schedule briefing for Kindle reading. "
        "The reader wants a quick, scannable overview — they're planning their day and week, "
        "not searching for details they'll look up later on their phone. "
        "Given this calendar data as JSON, return ONLY a raw JSON object — no markdown fences: "
        '{"today":[{"time":"...","title":"...","note":"..."}],'
        '"this_week":[{"day":"...","time":"...","title":"..."}],'
        '"past_reminders":[{"title":"...","was_due":"..."}],'
        '"conflicts":["..."]} '
        "Rules: "
        "today: all events for today. time in 12h format (e.g. '2:30 PM'). "
        "note: location if present, or attendee count if >2 people, or blank — pick one, not all three. "
        "this_week: events from tomorrow through 7 days out, sorted chronologically. "
        "day: short weekday name ('Mon', 'Tue', etc). Skip days with no events. "
        "past_reminders: reminders/tasks due in the last 3 days that appear unresolved. "
        "was_due: natural language ('yesterday', '2 days ago'). "
        "conflicts: list of plain-English descriptions of overlapping events today, if any. "
        "Example: 'Team standup (10 AM) overlaps with Product sync (9:45 AM–10:15 AM)'. "
        "Empty array if no conflicts. "
        "If a field has no content, return an empty array — never omit the key."
    )

    response = _call_ai(instruction, json.dumps(events), label="calendar-format")
    if not response:
        return None

    parsed = _extract_json(response, label="calendar-format")
    if not isinstance(parsed, dict):
        return None

    # Ensure all required keys are present
    for key in ("today", "this_week", "past_reminders", "conflicts"):
        if key not in parsed:
            parsed[key] = []

    return parsed


def _format_plain(events: dict) -> dict:
    """Plain-text fallback when Gemini is unavailable."""
    today_items = []
    for e in events.get("today", []):
        today_items.append({
            "time":  e.get("time", ""),
            "title": e.get("title", ""),
            "note":  e.get("location", "") or (
                f"{e['attendees']} attendees" if e.get("attendees", 0) > 2 else ""
            ),
        })

    this_week_items = []
    for e in events.get("upcoming", []):
        this_week_items.append({
            "day":   e.get("day", ""),
            "time":  e.get("time", ""),
            "title": e.get("title", ""),
        })

    past_items = []
    for e in events.get("past_reminders", []):
        past_items.append({
            "title":   e.get("title", ""),
            "was_due": e.get("was_due", ""),
        })

    return {
        "today":           today_items,
        "this_week":       this_week_items,
        "past_reminders":  past_items,
        "conflicts":       [],
    }


def _build_articles(formatted: dict, raw_events: dict) -> list[dict]:
    """Convert the formatted event dict into synthetic EPUB article dicts."""
    articles: list[dict] = []

    # Today article
    today_lines = _build_today_lines(formatted)
    if today_lines or raw_events.get("today"):
        articles.append({
            "title":    "Today",
            "source":   "Google Calendar",
            "url":      _CALENDAR_URL,
            "summary":  "",
            "content":  today_lines,
            "category": "Calendar",
        })

    # This Week article
    if formatted.get("this_week"):
        articles.append({
            "title":    "This Week",
            "source":   "Google Calendar",
            "url":      _CALENDAR_URL,
            "summary":  "",
            "content":  _build_week_lines(formatted),
            "category": "Calendar",
        })

    # Reminders article
    if formatted.get("past_reminders"):
        articles.append({
            "title":    "Reminders",
            "source":   "Google Calendar",
            "url":      _CALENDAR_URL,
            "summary":  "",
            "content":  _build_reminder_lines(formatted),
            "category": "Calendar",
        })

    return articles


def _build_today_lines(formatted: dict) -> str:
    lines = []
    for e in formatted.get("today", []):
        time_col = e.get("time", "").ljust(10)
        note = f"  ({e['note']})" if e.get("note") else ""
        lines.append(f"{time_col}{e.get('title', '')}{note}")

    conflicts = formatted.get("conflicts", [])
    if conflicts:
        lines.append("")
        for conflict in conflicts:
            lines.append(f"Warning  {conflict}")

    return "\n".join(lines)


def _build_week_lines(formatted: dict) -> str:
    lines = []
    for e in formatted.get("this_week", []):
        day_col = e.get("day", "").ljust(5)
        time_col = e.get("time", "").ljust(10)
        lines.append(f"{day_col}{time_col}{e.get('title', '')}")
    return "\n".join(lines)


def _build_reminder_lines(formatted: dict) -> str:
    lines = []
    for e in formatted.get("past_reminders", []):
        was_due = e.get("was_due", "").ljust(12)
        lines.append(f"{was_due}{e.get('title', '')}")
    return "\n".join(lines)
