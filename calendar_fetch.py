"""Fetch upcoming and recent events from Google Calendar."""
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from config import console
from google_auth import ALL_SCOPES, get_google_credentials

SCOPES = ALL_SCOPES

_EMPTY_RESULT = {"today": [], "upcoming": [], "past_reminders": []}


def get_calendar_events(lookahead_days: int, lookback_days: int) -> dict:
    """
    Fetch events from all Google Calendars the user has access to.

    Returns:
        {
            "today": [...],
            "upcoming": [...],
            "past_reminders": [...],
        }
    """
    creds = get_google_credentials(SCOPES)
    if creds is None:
        console.print(
            "  [yellow]⚠  credentials.json not found — skipping Calendar section[/yellow]"
        )
        return _EMPTY_RESULT

    try:
        service = build("calendar", "v3", credentials=creds)
        calendars = _list_calendars(service)

        local_now = datetime.now().astimezone()
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        upcoming_end = today_start + timedelta(days=lookahead_days + 1)
        lookback_start = today_start - timedelta(days=lookback_days)

        today_start_utc = today_start.astimezone(timezone.utc)
        today_end_utc = today_end.astimezone(timezone.utc)
        upcoming_end_utc = upcoming_end.astimezone(timezone.utc)
        lookback_start_utc = lookback_start.astimezone(timezone.utc)
        now_utc = datetime.now(tz=timezone.utc)

        today_events: list[dict] = []
        upcoming_events: list[dict] = []
        past_reminders: list[dict] = []

        for cal in calendars:
            cal_id = cal["id"]
            cal_name = cal.get("summary", cal_id)

            # Fetch today + upcoming in one query
            future_items = _fetch_events(
                service, cal_id,
                time_min=today_start_utc,
                time_max=upcoming_end_utc,
            )
            for event in future_items:
                start_dt, is_all_day = _parse_start(event)
                if start_dt is None:
                    continue
                start_local = start_dt.astimezone(local_now.tzinfo)
                if today_start <= start_local < today_end:
                    today_events.append(_to_today_event(event, cal_name, is_all_day))
                elif today_end <= start_local < upcoming_end:
                    upcoming_events.append(_to_upcoming_event(event, cal_name, is_all_day))

            # Fetch past events/reminders for lookback window
            past_items = _fetch_events(
                service, cal_id,
                time_min=lookback_start_utc,
                time_max=today_start_utc,
            )
            for event in past_items:
                end_dt = _parse_end(event)
                if end_dt is None:
                    continue
                past_reminders.append(_to_past_reminder(event, now_utc, end_dt))

        today_events.sort(key=lambda e: e.get("_sort_key", ""))
        upcoming_events.sort(key=lambda e: e.get("_sort_key", ""))

        # Strip internal sort keys
        for e in today_events:
            e.pop("_sort_key", None)
        for e in upcoming_events:
            e.pop("_sort_key", None)

        return {
            "today": today_events,
            "upcoming": upcoming_events,
            "past_reminders": past_reminders,
        }

    except Exception as exc:
        console.print(f"  [yellow]⚠  Calendar API error: {exc}[/yellow]")
        return _EMPTY_RESULT


# ── Helpers ───────────────────────────────────────────────────────────────────

def _list_calendars(service) -> list[dict]:
    try:
        result = service.calendarList().list().execute()
        return result.get("items", [])
    except Exception as exc:
        console.print(f"  [yellow]⚠  Could not list calendars: {exc}[/yellow]")
        return []


def _fetch_events(service, cal_id: str, time_min: datetime, time_max: datetime) -> list[dict]:
    try:
        result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        ).execute()
        return result.get("items", [])
    except Exception as exc:
        console.print(f"  [yellow]⚠  Could not fetch events for {cal_id}: {exc}[/yellow]")
        return []


def _parse_start(event: dict) -> tuple[datetime | None, bool]:
    """Return (start_datetime_utc, is_all_day)."""
    start = event.get("start", {})
    if "dateTime" in start:
        try:
            dt = datetime.fromisoformat(start["dateTime"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt, False
        except ValueError:
            return None, False
    if "date" in start:
        try:
            d = datetime.fromisoformat(start["date"]).replace(tzinfo=timezone.utc)
            return d, True
        except ValueError:
            return None, True
    return None, False


def _parse_end(event: dict) -> datetime | None:
    end = event.get("end", {})
    for key in ("dateTime", "date"):
        if key in end:
            try:
                dt = datetime.fromisoformat(end[key])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                return None
    return None


def _format_time_range(event: dict, is_all_day: bool) -> str:
    if is_all_day:
        return "All day"
    start = event.get("start", {}).get("dateTime", "")
    end = event.get("end", {}).get("dateTime", "")
    start_str = _fmt_time(start)
    end_str = _fmt_time(end)
    if start_str and end_str:
        return f"{start_str} – {end_str}"
    return start_str or "All day"


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%-I:%M %p").lstrip("0") or dt.strftime("%I:%M %p")
    except (ValueError, AttributeError):
        return ""


def _event_url(event: dict) -> str:
    return event.get("htmlLink") or "https://calendar.google.com"


def _attendee_count(event: dict) -> int:
    return len(event.get("attendees", []))


def _to_today_event(event: dict, cal_name: str, is_all_day: bool) -> dict:
    start_dt, _ = _parse_start(event)
    sort_key = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
    location = event.get("location", "")
    # Prefer hangout/meet link if location is absent
    if not location:
        location = event.get("hangoutLink", "")
    return {
        "title":      event.get("summary", "(No title)"),
        "time":       _format_time_range(event, is_all_day),
        "location":   location,
        "attendees":  _attendee_count(event),
        "url":        _event_url(event),
        "calendar":   cal_name,
        "_sort_key":  sort_key,
    }


def _to_upcoming_event(event: dict, cal_name: str, is_all_day: bool) -> dict:
    sort_key = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
    start_str = ""
    if not is_all_day:
        start_str = _fmt_time(event.get("start", {}).get("dateTime", ""))
    day_abbr = ""
    start = event.get("start", {})
    iso = start.get("dateTime") or start.get("date", "")
    try:
        dt = datetime.fromisoformat(iso)
        day_abbr = dt.strftime("%a")
    except ValueError:
        pass
    return {
        "title":     event.get("summary", "(No title)"),
        "day":       day_abbr,
        "time":      start_str or "All day",
        "url":       _event_url(event),
        "calendar":  cal_name,
        "_sort_key": sort_key,
    }


def _to_past_reminder(event: dict, now: datetime, end_dt: datetime) -> dict:
    delta = now - end_dt
    days_ago = delta.days
    if days_ago == 0:
        was_due = "earlier today"
    elif days_ago == 1:
        was_due = "yesterday"
    else:
        was_due = f"{days_ago} days ago"
    return {
        "title":   event.get("summary", "(No title)"),
        "was_due": was_due,
        "url":     _event_url(event),
    }
