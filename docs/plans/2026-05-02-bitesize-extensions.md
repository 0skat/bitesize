# Bitesize Extensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Bitesize with automatic Kindle delivery, Gmail and Calendar digest sections, and an Ollama backend as an alternative to Gemini CLI.

**Architecture:** Each new capability is added as a self-contained module with the same patterns already in the codebase — new sections feed into the existing `processed_sections` dict before EPUB generation; the AI backend is abstracted behind a thin interface so Gemini CLI and Ollama are interchangeable at runtime.

**Tech Stack:** Python 3, smtplib/email (Kindle delivery), Google APIs (Gmail + Calendar), Ollama REST API, existing Rich + EbookLib stack.

---

## Current State Reference

The pipeline today:
```
sources.json → select_sources() → fetch_feed() → fetch_article_content()
             → process_articles()  [Gemini]
             → generate_section_cover() [Gemini]
             → generate_global_cover()  [Gemini]
             → generate_epub()
             → ./output/<filename>.epub   ← no delivery, manual copy
```

After all four phases:
```
... → generate_epub() → send_to_kindle()   ← Phase 1
                      + gmail section      ← Phase 2
                      + calendar section   ← Phase 3
                      + Ollama backend     ← Phase 4
```

---

## Phase 1 — Kindle Delivery

**What:** After the EPUB is generated, automatically email it to the user's `@kindle.com` address via SMTP. Amazon's Send to Kindle accepts attachments from approved sender addresses.

**Files:**
- Create: `kindle.py` — single function `send_to_kindle(epub_path, config)`
- Modify: `config.py` — add `KINDLE_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (read from env)
- Modify: `main.py` — call `send_to_kindle()` after EPUB is written
- Create: `.env.example` — document required env vars

**Key decisions:**
- Credentials via environment variables only, never in `config.py` or `sources.json`
- Sender address must be pre-approved in Amazon's Kindle settings by the user
- Subject line and body don't matter; Amazon only looks at the attachment
- Fail gracefully with a clear error message if SMTP credentials are missing — don't abort the whole run

**Prompt design:** N/A — no AI involved in this phase.

---

## Phase 2 — Gmail Digest Section

**What:** Pull the user's last 24h of emails from Gmail, summarize and triage them with AI, and inject the result as a new `"Inbox"` section in the digest before EPUB generation.

**Files:**
- Create: `gmail.py` — authenticates with OAuth2, fetches recent threads, returns structured data
- Create: `gmail_processor.py` — AI summarization logic specific to email content
- Modify: `config.py` — add `GMAIL_MAX_THREADS`, `GMAIL_LOOKBACK_HOURS`
- Modify: `sources.json` — add optional `"gmail": true` toggle under a new top-level `"integrations"` key
- Modify: `main.py` — fetch Gmail section before EPUB generation if enabled
- Modify: `ui.py` — show Gmail as a toggle alongside RSS categories

**Key decisions:**
- Gmail uses OAuth2 (not API key). Credentials go in `credentials.json` (gitignored). Token cached in `token.json`.
- Fetch threads, not individual messages — a thread = one unit of context
- Strip quoted reply chains to avoid feeding the AI stale context
- The section is optional and off by default; user enables it in `sources.json` or via the UI

### Gmail AI Prompts

**Thread triage + summarization prompt** (called in batches, same pattern as `process_articles`):

```
You are a personal assistant reviewing email threads for a busy professional
reading a morning digest on their Kindle. They cannot act on emails right now —
this is for awareness only.

Review these email threads and return ONLY a raw JSON array, one object per thread:
[{"id": 0, "skip": false, "priority": "action|update|fyi", "summary": "..."}]

Rules:
- skip: true for automated notifications, receipts, marketing, newsletters,
  calendar invites with no context, and any thread with no human-written content
- priority:
    "action"  — someone is waiting for a response or decision (reply needed, approval, question)
    "update"  — meaningful update from a real person (project status, news from a colleague)
    "fyi"     — informational, no response needed
- summary: one sentence maximum. Lead with WHO and WHAT.
  Good: "Ana asked for feedback on the Q2 proposal by Friday."
  Bad:  "This email is about a proposal from Ana regarding Q2."
```

**Section cover prompt** for the Inbox section (mirrors `generate_section_cover`):

```
You are a personal assistant writing a one-page inbox briefing for a Kindle digest.
Based on these summarized email threads, write an inbox overview.
Return ONLY a raw JSON object — no markdown fences:
{"headline": "...", "editorial": "...", "top_stories": [{"title": "...", "one_liner": "..."}]}

Rules:
- headline: the single most important thing in the inbox today (max 12 words, no fluff)
  Good: "3 decisions needed before EOD, 1 from leadership"
  Bad:  "Your inbox summary for today"
- editorial: 2 sentences. First: overall inbox health (busy/quiet, action-heavy/informational).
  Second: the most important thread in one sentence.
- top_stories: exactly 3 items, priority "action" threads first, then "update".
  title: the thread subject. one_liner: the summary sentence from triage.
```

---

## Phase 3 — Google Calendar Section

**What:** Pull today's events plus the next 7 days from Google Calendar, format them with AI, and inject as a `"Calendar"` section. Also surface any reminders that passed in the last 3 days and weren't dismissed.

**Files:**
- Create: `calendar_fetch.py` — OAuth2 Google Calendar client, returns structured event data
- Create: `calendar_processor.py` — AI formatting logic for calendar events
- Modify: `config.py` — add `CALENDAR_LOOKAHEAD_DAYS`, `CALENDAR_LOOKBACK_DAYS`
- Modify: `sources.json` — add `"google_calendar": true` under `"integrations"`
- Modify: `main.py` — fetch calendar section if enabled
- Modify: `ui.py` — show Calendar as a toggle

**Key decisions:**
- Reuse the same `credentials.json` / `token.json` OAuth2 flow from Phase 2 (Google APIs share auth)
- Fetch from the user's primary calendar plus any calendars they've marked as visible
- Events are structured data (title, time, location, attendees, description) — send raw JSON to the AI, not HTML
- The AI's job here is formatting and flagging, not summarizing (events are already concise)

### Calendar AI Prompts

**Event formatting prompt** (single call, not batched — calendar data is small):

```
You are a personal assistant preparing a schedule briefing for Kindle reading.
The reader wants a quick, scannable overview — they're planning their day and week,
not searching for details they'll look up later on their phone.

Given this list of calendar events as JSON, return ONLY a raw JSON object:
{
  "today": [{"time": "...", "title": "...", "note": "..."}],
  "this_week": [{"day": "...", "time": "...", "title": "..."}],
  "past_reminders": [{"title": "...", "was_due": "..."}],
  "conflicts": ["..."]
}

Rules:
- today: all events for today. time in 12h format (e.g. "2:30 PM"). 
  note: location if present, or attendee count if >2 people, or blank — pick one, not all three.
- this_week: events from tomorrow through 7 days out, sorted chronologically.
  day: short weekday name ("Mon", "Tue", etc). Skip days with no events.
- past_reminders: reminders/tasks due in the last 3 days that appear unresolved.
  was_due: natural language ("yesterday", "2 days ago").
- conflicts: list of plain-English descriptions of overlapping events today, if any.
  Example: "Team standup (10 AM) overlaps with Product sync (9:45 AM–10:15 AM)"
  Empty array if no conflicts.
- If a field has no content, return an empty array — never omit the key.
```

**Section cover prompt** for the Calendar section:

```
You are a personal assistant writing a day-at-a-glance header for a Kindle digest.
Return ONLY a raw JSON object — no markdown fences:
{"headline": "...", "editorial": "...", "top_stories": [{"title": "...", "one_liner": "..."}]}

Rules:
- headline: characterize the day in max 10 words.
  Good: "Heavy meeting day — 5 events, 2 need prep"
  Good: "Light day — one afternoon call"
  Bad:  "Your calendar for today"
- editorial: 2 sentences. First: today's rhythm (back-to-back vs. space to work, etc.).
  Second: the most important or time-sensitive event this week.
- top_stories: the 3 most significant events (today first, then this week).
  title: event name. one_liner: time + any key context (who's joining, what to prepare).
```

---

## Phase 4 — Ollama Backend

**What:** Add Ollama as a fully interchangeable AI backend alongside Gemini CLI. The user picks the backend via a config flag or env var. Both backends accept the same prompts and return the same structured JSON — no changes needed in `main.py` or any caller.

**Files:**
- Create: `ollama_backend.py` — Ollama HTTP client, mirrors the interface of `gemini.py`
- Rename: `gemini.py` → `gemini_backend.py` (adjust imports)
- Create: `ai.py` — thin router: reads `AI_BACKEND` config, imports and delegates to the right backend
- Modify: `config.py` — add `AI_BACKEND` (`"gemini"` | `"ollama"`), `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`
- Modify: all callers (`main.py`, `gmail_processor.py`, `calendar_processor.py`) — import from `ai` instead of `gemini`
- Modify: `.env.example` — document Ollama vars

**Key decisions:**
- Ollama's API endpoint: `POST http://localhost:11434/api/generate` (non-streaming, `"stream": false`)
- The interface contract: both backends expose `process_articles()`, `generate_section_cover()`, `generate_global_cover()`, and (after Phase 2/3) `process_email_threads()`, `format_calendar_events()`, `generate_inbox_cover()`, `generate_calendar_cover()`
- Model selection matters: Ollama with a small model (e.g. `mistral:7b`) will produce lower-quality JSON than Gemini — recommend `llama3:8b` or larger in docs
- JSON reliability: Ollama models are less consistent at returning clean JSON. The existing `_extract_json()` fallback parser already handles this, but add a retry (once) on parse failure before falling back

### Ollama-specific prompt adjustments

The prompts from Phases 2 and 3 are written to be model-agnostic, but local models need more explicit framing. Wrap all Ollama prompts with:

```
[System]
You are a JSON-only assistant. You NEVER output prose, markdown, or explanation.
Every response is a single valid JSON object or array and nothing else.
Do not include ```json fences. Do not explain your reasoning. Output JSON only.

[User]
<existing prompt content here>
```

This wrapper is injected by `ollama_backend.py` automatically — callers don't need to think about it.

**Ollama availability check** (mirrors `_gemini_available()`):
```
GET http://{OLLAMA_HOST}/api/tags  → 200 means available
```

---

## Prompt Design Summary

| Section | Filter prompt | Summary/format prompt | Cover prompt |
|---|---|---|---|
| News (existing, improve) | Skip ads/sponsored only; real news always kept | 2 factual sentences, no editorialising | Punchy headline + 2-sentence editorial + 3 top stories |
| Inbox (Phase 2) | Skip automated, receipts, marketing | Priority triage + 1-sentence WHO/WHAT summary | Inbox health + most important thread |
| Calendar (Phase 3) | N/A — all events shown | Structured today/week/reminders/conflicts | Day characterization + rhythm + 3 key events |

**Shared principles across all prompts:**
- Always specify output format exactly before the content — models anchor to the first instruction
- Return raw JSON, no fences — the existing `_extract_json()` handles malformed output
- Lead with role framing ("You are a...") — improves focus
- For Kindle context: reader cannot act immediately, so tone is briefing/awareness, not urgent call-to-action
- Batch size stays at 20 for news; email threads at 10 (richer content per item); calendar is a single call

---

## Implementation Order & Dependencies

```
Phase 1 (Kindle delivery)     ← no dependencies, safe to start now
    ↓
Phase 2 (Gmail)               ← needs Google OAuth setup; independent of Phase 1
    ↓
Phase 3 (Calendar)            ← reuses OAuth from Phase 2; build after Phase 2
    ↓
Phase 4 (Ollama)              ← refactors AI layer; easiest after all sections exist
```

Phase 1 is fully independent. Phases 2 and 3 share OAuth infrastructure. Phase 4 is a horizontal refactor across everything, so doing it last means one clean pass.
