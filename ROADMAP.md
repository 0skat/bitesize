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
- **pt-BR tags** on each story: `resumo` vs `artigo-completo`, plus temas from a fixed list. Heuristics run when the AI is down.
- **Scoring:** fallback stays below 70; cover and section leads prefer AI scores over length stand-ins; clustered AI batches get one listwise re-rank.
- **A smaller, personal morning book.** `user_interests` scores stories on fit to the reader instead of general newsworthiness, on an absolute scale; `min_keep_score` and `max_articles_per_issue` trim the issue. Setting interests disables the forced score spread and the clustered listwise re-rank, both of which assume batch-relative scoring. `output_keep_issues` prunes `output/`.
- **Claude Code CLI backend** (`ai_backend=claude`), on the existing two-function transport contract. Uses the operator's subscription unless `ANTHROPIC_API_KEY` is set.
- **Spanish labels**, and `summary_language` splits summary language from book chrome (`source` keeps each summary in its article's own language).
- **Open-source hygiene:** MIT license, `SECURITY.md`, pytest + coverage + pip-audit + gitleaks CI, Dependabot, GitHub issue templates.

The dashboard **Preview** tab now loads live headlines per source. Still missing: last-digest preview, AI summary preview, magazine cover preview.

## Next

1. **Safari Reader on a rendered page.** A static Readability pass on the same GET bytes did **not** beat trafilatura (DROP — [experiment note](docs/research/2026-08-30-reader-extract-experiment.md)). The remaining bet is headless render, then extract. Background: [Safari Reader note](docs/research/2026-08-30-safari-reader-paywall.md).

2. **Dashboard previews (still open).** Last digest, a sample AI summary, and the cover JPEG before send. Headline-per-source preview is already in the Preview tab.

3. **Hourly pool, two builds a day.** Fetch through the day; assemble a short morning book and a short evening book. Mentioned as the next plan, not written yet.

4. **Gmail and Calendar on the daily run.** Code is ready; flags are still off. Needs Google OAuth files on the machine (`credentials.json` / `token.json`).

5. **Stock-Kindle navigation, not scripts.** Internal links, a better opening page, maybe clippings later. JavaScript, forms, and quizzes will not run on an unmodified Kindle — see `docs/research/2026-08-14-kindle-interactive-epub.md`.

6. **Kindle library cleanup is manual.** Amazon has no auto-delete for Send-to-Kindle personal documents. See [docs/research/2026-08-30-kindle-auto-delete.md](docs/research/2026-08-30-kindle-auto-delete.md).

## Later

- Fail-closed dashboard reads on a shared Mac (writes already need a token).
- Wordflow as its own product, or dropped. It is not part of the digest.

## Won't

- Interactive EPUB quizzes or in-book JavaScript on stock Kindle.
- Treating RSS URLs as untrusted-by-default (this is a personal digest; you pick the feeds).
