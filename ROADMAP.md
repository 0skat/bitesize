# Roadmap

What the digest does today, and what is worth building next. Bugs and flakes live in [ISSUES.md](ISSUES.md).

## Shipped

The morning pipeline is in daily use: RSS → full text → AI filter/summarize/score → magazine EPUB → Kindle email and iCloud Books.

- **Settings live in SQLite** (`data/bitesize.db`), edited from the local dashboard. `.env` / `sources.json` only seed an empty database.
- **Three AI backends:** Antigravity (`agy`, default), Gemini CLI, Ollama. If none answer, the EPUB still writes with length-based scores and no summaries.
- **pt-BR labels and prompts** (`ai_locale.py`). Language is a setting, not a rewrite of the pipeline.
- **Paywall mirrors** when the direct fetch is thin or fails.
- **Gmail and Calendar sections** are wired in `main.py` and off by default. Enable them in the dashboard; the daily `--all` run will pick them up.
- **macOS LaunchAgent** at 06:50 (`scripts/install-daily-launchd.sh`).
- **Open-source hygiene** on this branch: MIT license, `SECURITY.md`, pytest + pip-audit + gitleaks CI. Not on `main` yet, and there is no git remote.

Dashboard footer still lists three previews it does not have: content, AI summaries, magazine covers. Those belong below, not in ISSUES.

## Next

1. **A smaller morning book.** Daily runs land 120–140 articles. Relevance sorting exists; a tighter keep-list or a “top stories only” EPUB would make the Kindle actually readable.
2. **Dashboard previews.** Show the last digest, a sample summary, and the cover JPEG before send. The UI already names this backlog.
3. **Hourly pool, two builds a day.** Fetch through the day; assemble a short morning book and a short evening book. Mentioned as the next plan, not written yet.
4. **Gmail and Calendar on the daily run.** Code is ready; flags are still off. Needs Google OAuth files on the machine (`credentials.json` / `token.json`).
5. **Stock-Kindle navigation, not scripts.** Internal links, a better opening page, maybe clippings later. JavaScript, forms, and quizzes will not run on an unmodified Kindle — see `docs/research/2026-08-14-kindle-interactive-epub.md`.

## Later

- Dependabot and a public GitHub repo (the pre-publish checklist in README).
- Fail-closed dashboard reads on a shared Mac (writes already need a token).
- Wordflow as its own product, or dropped. It is not part of the digest.

## Won't

- Interactive EPUB quizzes or in-book JavaScript on stock Kindle.
- Treating RSS URLs as untrusted-by-default (this is a personal digest; you pick the feeds).
