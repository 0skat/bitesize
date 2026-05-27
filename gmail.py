"""Fetch recent email threads from Gmail via the Google API."""
import base64
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build

from config import console
from google_auth import get_google_credentials

_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Matches the start of a quoted reply block (e.g. "On Mon, Jan 6, Alice wrote:")
_QUOTE_HEADER_RE = re.compile(r"^On .{0,200} wrote:\s*$", re.MULTILINE)

_BODY_MAX_CHARS = 2000


def get_gmail_threads(max_threads: int, lookback_hours: int) -> list[dict]:
    """
    Fetch recent Gmail threads.

    Returns a list of dicts:
        {
            "thread_id": str,
            "subject":   str,
            "sender":    str,
            "date":      str,   # "Mon Jan 6, 2:30 PM"
            "body":      str,
            "url":       str,
        }
    Returns [] if credentials are missing or on any API error.
    """
    creds = get_google_credentials([_GMAIL_SCOPE])
    if creds is None:
        console.print(
            "  [yellow]⚠  Gmail credentials.json not found — skipping Gmail section[/yellow]"
        )
        return []

    try:
        service = build("gmail", "v1", credentials=creds)
        return _fetch_threads(service, max_threads, lookback_hours)
    except Exception as exc:
        console.print(f"  [yellow]⚠  Gmail API error: {exc}[/yellow]")
        return []


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fetch_threads(service, max_threads: int, lookback_hours: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    # Gmail query: threads newer than the lookback window, in inbox
    after_ts = int(cutoff.timestamp())
    query = f"in:inbox after:{after_ts}"

    list_response = (
        service.users()
        .threads()
        .list(userId="me", q=query, maxResults=max_threads)
        .execute()
    )

    raw_threads = list_response.get("threads", [])
    results: list[dict] = []

    for raw in raw_threads:
        try:
            thread_data = (
                service.users()
                .threads()
                .get(userId="me", id=raw["id"], format="full")
                .execute()
            )
            parsed = _parse_thread(thread_data)
            if parsed:
                results.append(parsed)
        except Exception as exc:
            console.print(f"  [yellow]⚠  Could not fetch thread {raw['id']}: {exc}[/yellow]")

    return results


def _parse_thread(thread_data: dict) -> dict | None:
    messages = thread_data.get("messages", [])
    if not messages:
        return None

    first_msg = messages[0]
    headers = {
        h["name"].lower(): h["value"]
        for h in first_msg.get("payload", {}).get("headers", [])
    }

    subject = headers.get("subject", "(no subject)")
    sender = headers.get("from", "unknown")
    date_str = headers.get("date", "")
    thread_id = thread_data["id"]

    date_formatted = _format_date(date_str)

    # Use the last message body (most recent reply) as the representative body
    last_msg = messages[-1]
    body = _extract_body(last_msg.get("payload", {}))
    body = _strip_quoted_replies(body)
    body = body[:_BODY_MAX_CHARS]

    return {
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "date": date_formatted,
        "body": body,
        "url": f"https://mail.google.com/mail/u/0/#inbox/{thread_id}",
    }


def _extract_body(payload: dict) -> str:
    """
    Recursively extract plain text from a MIME payload.
    Prefers text/plain; falls back to text/html (stripped of tags).
    """
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return _decode_body_data(payload.get("body", {}).get("data", ""))

    if mime_type == "text/html":
        raw_html = _decode_body_data(payload.get("body", {}).get("data", ""))
        return _strip_html(raw_html)

    if "parts" in payload:
        plain_text = ""
        html_fallback = ""
        for part in payload["parts"]:
            part_mime = part.get("mimeType", "")
            if part_mime == "text/plain":
                plain_text = _decode_body_data(part.get("body", {}).get("data", ""))
            elif part_mime == "text/html" and not plain_text:
                html_fallback = _strip_html(
                    _decode_body_data(part.get("body", {}).get("data", ""))
                )
            elif part_mime.startswith("multipart/"):
                nested = _extract_body(part)
                if nested:
                    plain_text = plain_text or nested
        return plain_text or html_fallback

    return ""


def _decode_body_data(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _strip_html(html: str) -> str:
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "lxml").get_text(separator="\n")
    except Exception:
        # Fallback: naive tag strip
        return re.sub(r"<[^>]+>", " ", html)


def _strip_quoted_replies(text: str) -> str:
    """
    Remove quoted reply blocks:
    - Anything after "On ... wrote:" line
    - Lines starting with ">" (inline quoting)
    """
    match = _QUOTE_HEADER_RE.search(text)
    if match:
        text = text[: match.start()].rstrip()

    lines = [line for line in text.splitlines() if not line.startswith(">")]
    return "\n".join(lines).strip()


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%a %b %-d, %-I:%M %p")
    except Exception:
        return date_str
