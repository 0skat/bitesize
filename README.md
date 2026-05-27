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

# Non-interactive — all RSS sources
python main.py --all --no-kindle

# EPUB only, no email
python main.py --no-kindle
```

Output lands in `./output/News Digest - <date>.epub`.

### Previewing on a real Kindle layout

Apple Books, Calibre, and browser-based EPUB viewers use different pagination, margins, and fonts than e-ink Kindles. **They are useful for a quick sanity check, but they are not faithful to what you see on a device.**

For a close match to your Kindle (including Send-to-Kindle conversion), use Amazon’s free **[Kindle Previewer 3](https://www.amazon.com/gp/feature.html?docId=1003018611)** (macOS / Windows): open the generated `.epub` there before judging typography or “page 1”.

## Configuration

| File | Purpose |
|------|---------|
| `sources.json` | RSS categories, feeds, integration toggles |
| `.env` | Kindle SMTP, AI backend, Gmail/Calendar limits |
| `credentials.json` | Google OAuth client (gitignored; needed for Gmail/Calendar) |

To enable Gmail or Calendar, set `"gmail": true` or `"google_calendar": true` under `"integrations"` in `sources.json`.

## Project layout

| Module | Role |
|--------|------|
| `main.py` | CLI entry point and pipeline orchestration |
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
