# CLAUDE.md

Agent entrypoint for BiteSIze. Humans start at [README.md](README.md). Direction lives in [ROADMAP.md](ROADMAP.md). Known problems live in [ISSUES.md](ISSUES.md).

## Truth hierarchy

| Rank | Source | Use for |
|------|--------|---------|
| 1 | Code + `tests/` | What actually runs |
| 2 | `data/bitesize.db` | Live settings and RSS sources (gitignored) |
| 3 | This file | How to work here |
| 4 | [ISSUES.md](ISSUES.md) / [ROADMAP.md](ROADMAP.md) | Current problems and direction |
| 5 | [README.md](README.md) | Human setup |
| — | `docs/superpowers/plans/` | Historical plans — **check code before treating a finding as open** |

`.env` and `sources.json` are **seed only**. After the first migrate they are not the runtime source of truth.

## Before you change anything

1. Read [ISSUES.md](ISSUES.md) if the work is a bug or a flake.
2. Read [ROADMAP.md](ROADMAP.md) if the work is a feature.
3. Confirm the setting you care about in the dashboard or `data/bitesize.db`, not in `.env`.

## Commands

```bash
source .venv/bin/activate
pytest tests/ -v
python dashboard.py          # http://127.0.0.1:8765
python main.py --all         # full digest
python main.py --all --no-kindle --no-books
```

Write APIs on the dashboard need `Authorization: Bearer <token>`. Token is `DASHBOARD_TOKEN` or `data/dashboard.token` (auto-created). The UI field stores it in localStorage.

Daily run: `scripts/install-daily-launchd.sh` → `main.py --all` at 06:50. Logs: `output/logs/digest-stdout.log`.

## Pipeline

`main.py` is the only orchestrator:

RSS (parallel) → full text + paywall mirrors → AI filter/summarize/score → section + global covers → EPUB → Kindle SMTP → iCloud Books.

Gmail and Calendar inject extra sections when their integration flags are on. The daily LaunchAgent uses `--all`, so it honors those flags from the database and does not prompt.

AI calls go through `ai.py` (`claude` / `antigravity` / `gemini` / `ollama` — note the router falls through to Gemini on any unrecognised value). Prompts live in `gemini.py` plus the Gmail/Calendar processors. If the backend is down, the digest still writes: length-based relevance, no summaries.

Relevance has two modes, and this matters before touching scoring. With `user_interests` empty it is upstream's batch-relative newsworthiness score, with a forced spread and a listwise re-rank for clustered batches. With `user_interests` set it is an absolute per-story fit score, and both the forced spread and the listwise re-rank are deliberately disabled (`gemini._relevance_rule`, `gemini._maybe_remap_clustered_batch`) — re-enabling either would break `min_keep_score`. The keep-list and the `output/` prune live in `main.py` (`_apply_interest_filter`, `_prune_old_issues`).

## Conventions

- **Single-user local tool.** Dashboard binds `127.0.0.1`. Do not expose it.
- **Secrets stay off git:** `.env`, `data/`, `token.json`, `credentials.json`, `output/`.
- **Tests first** for behavior changes. `pytest tests/ -v` is the gate.
- **Delivery is best-effort.** Kindle/Books failures must not abort EPUB write.
- **Stock Kindle has no JavaScript.** Internal links, covers, and reflowable HTML only. See `docs/research/2026-08-14-kindle-interactive-epub.md` before promising interactivity.
- **Safari Reader** — planned, not built. See [ROADMAP.md](ROADMAP.md) item 1 and `docs/research/2026-08-30-safari-reader-paywall.md`.
- **The topic vocabulary stays pt-BR.** `tags.TEMAS` is the canonical set and its keys are pt-BR; do not invent new topic labels. Rendering those keys for a reader is separate: `EPUB_LABELS[<lang>]["tema_*"]` holds display strings per language, and `en` / `es` now translate them. Add a display label, never a vocabulary entry.
- **`wordflow/`** is a separate experimental Next.js app. Do not treat it as part of the digest unless the task names it.
- **Published default is `main`.** `upstream` is `https://github.com/victor-salles/bitesize`; this fork's own work goes to `origin`. Keep fork changes additive and confined to small files so they rebase on upstream. Do not commit `.env`, `data/`, or `output/`.

## Put down

When a run, review, or fix changes what is true, update [ISSUES.md](ISSUES.md) or [ROADMAP.md](ROADMAP.md) in the same change. Do not grow this file with status.
