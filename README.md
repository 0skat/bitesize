# BiteSIze

AI-powered personal news digest that fetches RSS feeds (and optional Gmail/Calendar), summarizes articles, builds a Kindle-friendly EPUB, and emails it to your device.

## What it does

```
sources.json → select sources → fetch RSS + full article text
             → AI filter/summarize → section + global covers
             → EPUB in ./output/ → email to Kindle (optional)
```

Optional integrations (off by default in `sources.json`):

- **Gmail** — last 24h of inbox threads, triaged and summarized
- **Google Calendar** — today + next 7 days, formatted for reading

## Quick start

### 1. Python environment

Run each command separately (do not paste inline comments):

```bash
cd bitesize
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. AI backend (pick one)

**Ollama (recommended for local use)**

```bash
# Install Ollama from https://ollama.com, then pull a model:
ollama pull gemma4:e4b   # or llama3:8b, mistral, etc.
```

Set in `.env` (use a model you have installed — check with `ollama list`):

```
AI_BACKEND=ollama
OLLAMA_MODEL=gemma4:e4b
```

**Gemini CLI**

Requires Node.js/npm. Install globally:

```bash
brew install node
npm install -g @google/gemini-cli
gemini --version
```

On first use, authenticate when prompted (`gemini` opens a browser login). Then set in `.env`:

```
AI_BACKEND=gemini
```

Note: Google is restricting free Gemini CLI access after June 2026; Ollama remains a reliable local fallback.

If neither backend is available, the digest still runs — articles are kept without AI summaries or covers.

### 3. Kindle delivery (optional)

Edit `.env` with your `@kindle.com` address and Gmail SMTP credentials.

**Gmail App Password (required — not your normal Gmail password):**

1. Open [Google App Passwords](https://myaccount.google.com/apppasswords) (2-Step Verification must be on).
2. Create an app password for "Mail" / "Other (BiteSIze)".
3. Copy the 16-character password into `.env`:

```
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
```

4. Whitelist `SMTP_USER` in Amazon Kindle → Personal Document Settings → Approved senders.

Skip delivery with `--no-kindle`.

### 4. Run

```bash
# Interactive — pick categories and sources
python main.py

# Non-interactive — all RSS sources, build EPUB and email Kindle
python main.py --all

# EPUB only (no SMTP)
python main.py --all --no-kindle
```

Output lands in `./output/News Digest - <date>.epub`.

### Relevance scores

Each article receives a **0–100 relevance** score from the AI (or a simple fallback from article length when the model omits a score). The EPUB **sorts each section highest-first**, prints the score under the “Summary” heading on article pages, shows it on section index cards, and adds a **“Top stories by relevance”** block on the digest front page so the most important items are easy to find.

### Daily run at 6:50 AM (macOS)

On your Mac, install a LaunchAgent (runs in your GUI session; the machine must be awake and logged in at 6:50):

```bash
./scripts/install-daily-launchd.sh
```

This writes `~/Library/LaunchAgents/com.bitesize.digest.plist`, runs `.venv/bin/python main.py --all` every day at **06:50** local time (so the digest is ready and syncing to iPhone by ~7:00), emails the EPUB to Kindle (when configured), copies it to your **iCloud Books** library (when iCloud Books is enabled on the Mac), and appends logs to `output/logs/digest-stdout.log` and `digest-stderr.log`.

If auto-detection cannot find your Books folder, set `icloud_books_dir` in the dashboard (typical path: `~/Library/Mobile Documents/iCloud~com~apple~iBooks/Documents`).

Uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.bitesize.digest.plist
rm ~/Library/LaunchAgents/com.bitesize.digest.plist
```

### Previewing on a real Kindle layout

Apple Books, Calibre, and browser-based EPUB viewers use different pagination, margins, and fonts than e-ink Kindles. **They are useful for a quick sanity check, but they are not faithful to what you see on a device.**

For a close match to your Kindle (including Send-to-Kindle conversion), use Amazon’s free **[Kindle Previewer 3](https://www.amazon.com/gp/feature.html?docId=1003018611)** (macOS / Windows): open the generated `.epub` there before judging typography or “page 1”.

## Configuration

Settings are stored in **`data/bitesize.db`** (SQLite). The CLI and dashboard share this database.

### Settings dashboard

```bash
python dashboard.py
# → http://127.0.0.1:8765
```

Use the web UI to edit AI, feed, EPUB, Kindle SMTP, integrations, and RSS sources. On first run, existing `sources.json` and `.env` values are imported automatically.

| File | Purpose |
|------|---------|
| `data/bitesize.db` | All runtime settings and RSS sources (primary) |
| `sources.json` | Legacy seed file — imported once if DB is empty |
| `.env` | Legacy seed file — imported once if DB is empty |
| `credentials.json` | Google OAuth client (gitignored; needed for Gmail/Calendar) |

To enable Gmail or Calendar, set `"gmail": true` or `"google_calendar": true` under `"integrations"` in `sources.json`.

## Project layout

| Module | Role |
|--------|------|
| `main.py` | CLI entry point and pipeline orchestration |
| `dashboard.py` | Local settings dashboard (Flask + HTML UI) |
| `settings_store.py` | SQLite settings and RSS source storage |
| `feed.py` | RSS fetch, article extraction, headline filtering |
| `gemini.py` | AI prompts for news (uses `ai.py` router) |
| `ai.py` | Routes to Gemini CLI or Ollama |
| `epub.py` | Kindle-optimized EPUB generation |
| `kindle.py` | SMTP delivery to `@kindle.com` |
| `gmail.py` / `gmail_processor.py` | Gmail integration |
| `calendar_fetch.py` / `calendar_processor.py` | Calendar integration |
| `ui.py` | Interactive source/integration selection |

## Notes

- RSS fetching uses `requests` + `certifi` so feeds work on macOS Python installs where `feedparser.parse(url)` fails SSL verification.
- There is also a legacy Node.js script (`bitesize.js`) for topic exploration — separate from the Python Kindle digest.
- Feature branches (`feature/phase1-*` through `feature/phase4-ollama`) contain the incremental history; `main` consolidates all four phases.

## Open source

BiteSIze is MIT-licensed. See [LICENSE](LICENSE), [SECURITY.md](SECURITY.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

**Before your first run:** copy `.env.example` → `.env`, run `python dashboard.py` to configure settings, or let the CLI migrate from `.env`/`sources.json` once.

**Security notes:**

- Dashboard binds to `127.0.0.1:8765` only.
- Set `DASHBOARD_TOKEN` to protect write APIs on shared machines.
- RSS feed URLs are fetched as the local user — only add feeds you trust.
- `wordflow/` is an experimental subproject; do not expose it publicly without auth.

## Pre-publish checklist (maintainers)

- [ ] No `.env`, `data/`, `token.json`, or `credentials.json` in git
- [ ] PII scan clean on tracked files (`rg -i 'your-email|/Users/you' --glob '!data/**'`)
- [ ] `pytest tests/ -v` passes
- [ ] `pip-audit -r requirements.txt` clean or documented exceptions
- [ ] LICENSE + SECURITY.md present
- [ ] GitHub repo set to public with security advisories enabled
