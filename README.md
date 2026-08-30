# BiteSIze

AI-powered personal news digest that fetches RSS feeds (and optional Gmail/Calendar), summarizes articles, builds a magazine-style Kindle EPUB, and delivers it to Kindle and iCloud Books.

| Doc | For |
|-----|-----|
| [CLAUDE.md](CLAUDE.md) | Agents working in this repo |
| [ROADMAP.md](ROADMAP.md) | What is shipped vs what comes next |
| [ISSUES.md](ISSUES.md) | Known problems (GitHub Issues after the repo is public) |
| [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md) | Dev commands and tests |

## What it does

```
SQLite sources → fetch RSS (parallel)
              → full article text (paywall mirrors on failure)
              → AI batch filter / summarize / score
              → magazine cover + section layers → EPUB in ./output/
              → Kindle SMTP (optional) + iCloud Books copy (optional)
```

Optional integrations (off by default — enable in the dashboard):

- **Gmail** — recent inbox threads, triaged and summarized
- **Google Calendar** — upcoming events formatted for reading

## Quick start

### 1. Python environment

```bash
cd bitesize
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Settings

**Dashboard (recommended)**

```bash
python dashboard.py
# → http://127.0.0.1:8765
```

Edit AI backend, RSS sources, Kindle SMTP, language, and delivery flags. On first run, values from `sources.json` and `.env` are imported into `data/bitesize.db`.

Write APIs always need a Bearer token. The dashboard creates one at `data/dashboard.token` if `DASHBOARD_TOKEN` is not set in `.env`. Paste that token into the “Write API token” field (the browser remembers it). GET reads stay open on localhost.

### 3. AI backend (pick one)

Defaults in the database: **Antigravity** (`agy`) with `gemini-3.5-flash-high`, summaries in **pt-BR**. Change the model in the dashboard if you want a different one.

**Antigravity (default)**

Requires the `agy` CLI installed and authenticated. Set in the dashboard or `.env`:

```
AI_BACKEND=antigravity
ANTIGRAVITY_MODEL=gemini-3.5-flash-high
AI_LANGUAGE=pt-BR
```

**Ollama (local)**

```bash
ollama pull llama3:8b
```

```
AI_BACKEND=ollama
OLLAMA_MODEL=llama3:8b
```

**Gemini CLI**

```bash
npm install -g @google/gemini-cli
```

```
AI_BACKEND=gemini
```

If no backend is available, the digest still runs — articles are kept with length-based relevance fallbacks and no AI summaries.

### 4. Kindle delivery (optional)

Edit `.env` or the dashboard with your `@kindle.com` address and Gmail SMTP credentials.

**Gmail App Password (required — not your normal Gmail password):**

1. Open [Google App Passwords](https://myaccount.google.com/apppasswords) (2-Step Verification must be on).
2. Create an app password for Mail.
3. Copy the 16-character password into `.env` or the dashboard.

4. Whitelist `SMTP_USER` in Amazon Kindle → Personal Document Settings → Approved senders.

Skip delivery with `--no-kindle`.

Amazon does **not** auto-delete old Send-to-Kindle personal documents. Each morning’s file has a new name, so it stacks in your library. Periodically delete old “Resumo de Notícias” docs in [Manage Your Content and Devices](https://www.amazon.com/mycd) (filter **Docs**), then sync the Kindle. Details: [docs/research/2026-08-30-kindle-auto-delete.md](docs/research/2026-08-30-kindle-auto-delete.md).

### 5. iCloud Books (optional)

When `books_delivery_enabled` is true (default), the EPUB is copied to your Mac iCloud Books folder so it syncs to iPhone/iPad. Skip with `--no-books`.

Typical path: `~/Library/Mobile Documents/iCloud~com~apple~iBooks/Documents` — set `icloud_books_dir` in the dashboard if auto-detection fails.

### 6. Run

```bash
# Interactive — pick categories and sources
python main.py

# Non-interactive — all RSS sources
python main.py --all

# EPUB only (no Kindle, no iCloud Books)
python main.py --all --no-kindle --no-books
```

Output lands in `./output/` (filename follows `ai_language`, e.g. `Resumo de Notícias - …` for pt-BR).

### Relevance scores

Each article gets a **0–100** relevance score from the AI (or a length-based fallback). The EPUB **sorts sections highest-first**, shows scores as **0–10** on article pages and top picks, and builds a **“Top stories”** block on the opening page.

### Paywall bypass

When direct article fetch fails or returns too little text, BiteSIze tries archive mirrors (archive.is → 1ft.io → archive.org → removepaywall.com). Success rates are logged to `output/logs/paywall-stats.log` after each run.

### Daily run at 6:50 AM (macOS)

```bash
./scripts/install-daily-launchd.sh
```

Runs `.venv/bin/python main.py --all` every day at **06:50** local time (digest ready by ~07:00), emails Kindle when configured, copies to iCloud Books, and logs to `output/logs/digest-stdout.log`.

Uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.bitesize.digest.plist
rm ~/Library/LaunchAgents/com.bitesize.digest.plist
```

### Previewing on a real Kindle layout

Apple Books, Calibre, and browser EPUB viewers differ from e-ink Kindles. For a close match, use Amazon’s free **[Kindle Previewer 3](https://www.amazon.com/gp/feature.html?docId=1003018611)**.

## Configuration

Settings live in **`data/bitesize.db`** (SQLite). The CLI and dashboard share this database.

| File | Purpose |
|------|---------|
| `data/bitesize.db` | All runtime settings and RSS sources (primary) |
| `sources.json` | Legacy seed — imported once if DB is empty |
| `.env` | Legacy seed — imported once if DB is empty |
| `credentials.json` | Google OAuth client (gitignored; Gmail/Calendar) |

Enable Gmail or Calendar under **Integrations** in the dashboard (or set `integration_gmail` / `integration_google_calendar` in settings).

## Project layout

| Module | Role |
|--------|------|
| `main.py` | CLI entry point and pipeline orchestration |
| `dashboard.py` | Local settings dashboard (Flask + HTML UI) |
| `settings_store.py` | SQLite settings and RSS source storage |
| `feed.py` | RSS fetch, article extraction, headline filtering |
| `paywall.py` | Archive mirror fallback for paywalled articles |
| `gemini.py` | AI prompts for news (uses `ai.py` router) |
| `ai.py` | Routes to Antigravity, Gemini CLI, or Ollama |
| `antigravity_backend.py` | `agy` CLI subprocess backend |
| `ai_locale.py` | pt-BR (and other) EPUB labels and AI language rules |
| `epub.py` | Kindle-optimized EPUB generation |
| `cover_art.py` | Magazine-style JPEG cover for library thumbnail |
| `magazine_layers.py` | Hero story, teasers, desk highlights (deduped layers) |
| `kindle.py` | SMTP delivery to `@kindle.com` |
| `books.py` | Copy EPUB to iCloud Books library |
| `sources_selection.py` | CLI `--all` vs interactive source picking |
| `gmail.py` / `gmail_processor.py` | Gmail integration |
| `calendar_fetch.py` / `calendar_processor.py` | Calendar integration |
| `ui.py` | Interactive source/integration selection |

## Notes

- RSS fetching uses `requests` + `certifi` for reliable TLS on macOS Python.
- AI processing batches articles (`gemini_batch_size`, default 20) for fewer, cheaper calls.
- Legacy Node script `bitesize.js` exists for topic exploration — separate from the Python digest.
- See [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md) for dev commands and tests.

## Open source

BiteSIze is MIT-licensed. See [LICENSE](LICENSE), [SECURITY.md](SECURITY.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

**Before your first run:** copy `.env.example` → `.env`, run `python dashboard.py` to configure settings, or let the CLI migrate from `.env`/`sources.json` once.

**Security notes:**

- Dashboard binds to `127.0.0.1:8765` only.
- Write APIs require a Bearer token (`DASHBOARD_TOKEN` or `data/dashboard.token`).
- RSS feed URLs are fetched as the local user — only add feeds you trust.
- `wordflow/` is an experimental subproject; do not expose it publicly without auth.

## Pre-publish checklist (maintainers)

- [ ] No `.env`, `data/`, `token.json`, or `credentials.json` in git
- [ ] PII scan clean on tracked files (`rg -i 'your-email|/Users/you' --glob '!data/**'`)
- [ ] `pytest tests/ -v --cov` passes (CI gate is 45% line coverage; Gmail/Calendar/CLI are mostly untested)
- [ ] `pip-audit -r requirements.txt` clean or documented exceptions
- [ ] LICENSE + SECURITY.md present
- [ ] GitHub repo set to public with security advisories enabled
- [ ] Dependabot alerts on; first CI run green (pytest + coverage + pip-audit + gitleaks)
