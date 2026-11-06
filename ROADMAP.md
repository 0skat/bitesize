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
- **Runs on a Raspberry Pi.** `scripts/move-to-pi.sh` moves the install from the Mac; `scripts/install-linux-systemd.sh` sets up the dashboard service and a persistent 06:50 timer. iCloud Books is macOS-only, so the Issue tab's **Download EPUB** (`/api/issues/<id>/epub`, `/api/issues/latest/epub`) replaces it on Linux. `scripts/deploy-to-pi.sh` ships later changes, with tests on the Pi and rollback on failure.
- **Freshness.** `max_article_age_days` drops stale feed items before the title screen, and `seen_memory_days` never offers a URL that has already been in a pool. Both default to 0 (upstream behaviour); `seen.forget(url)` undoes a mistake.
- **Brave Search as a source** (`brave_enabled`). `brave_mode=supplement` adds it to the RSS feeds, `primary` uses it alone. Queries are one `Section = query` line each, `freshness=pd` bounds results to the last day at the source, and `site:reuters.com` reaches publishers with no usable feed. Results enter the same pipeline as RSS, so dedupe, the age filter and the screen all apply. `scripts/brave-probe.py` shows what comes back without storing anything or calling the AI.
- **pt-BR tags** on each story: `resumo` vs `artigo-completo`, plus temas from a fixed list. Heuristics run when the AI is down.
- **Scoring:** fallback stays below 70; cover and section leads prefer AI scores over length stand-ins; clustered AI batches get one listwise re-rank.
- **A smaller, personal morning book.** `user_interests` scores stories on fit to the reader instead of general newsworthiness, on an absolute scale; `min_keep_score` and `max_articles_per_issue` trim the issue. Setting interests disables the forced score spread and the clustered listwise re-rank, both of which assume batch-relative scoring. `output_keep_issues` prunes `output/`.
- **Two-phase runs with human picking.** `--pool` fetches and screens only (2 AI calls, no downloads); the dashboard's Pool tab swipes through the candidates; `--build` summarises just the keepers. The daily LaunchAgent builds a pool and publishes nothing, so curation is required rather than optional. Partly delivers the old "hourly pool" idea.
- **Issue review.** Each run records its picks; the dashboard's Issue tab drops stories and rebuilds the EPUB without another AI pass.
- **Balanced issues.** `balance_sections` fills the cap round-robin across sections and `min_section_stories` admits each section's best few below `min_keep_score`, which is what actually stopped whole interest areas vanishing. `overflow_section_max` publishes the losers as a trailing "Also considered" section.
- **Two-pass filtering.** `prefilter_keep` screens titles (sixty per AI call) before any body fetch, so only likely-relevant stories are fetched and summarised. Cross-feed duplicates are dropped in the same pass.
- **Claude Code CLI backend** (`ai_backend=claude`), on the existing two-function transport contract. Uses the operator's subscription unless `ANTHROPIC_API_KEY` is set.
- **Spanish labels**, and `summary_language` splits summary language from book chrome (`source` keeps each summary in its article's own language).
- **Open-source hygiene:** MIT license, `SECURITY.md`, pytest + coverage + pip-audit + gitleaks CI, Dependabot, GitHub issue templates.

The dashboard **Preview** tab loads live headlines per source, and the **Issue** tab shows what the last runs picked with their summaries and scores. Still missing: a magazine cover preview before send.

## Next

1. **Safari Reader on a rendered page.** A static Readability pass on the same GET bytes did **not** beat trafilatura (DROP — [experiment note](docs/research/2026-08-30-reader-extract-experiment.md)). The remaining bet is headless render, then extract. Background: [Safari Reader note](docs/research/2026-08-30-safari-reader-paywall.md).

2. **Dashboard previews (still open).** Last digest, a sample AI summary, and the cover JPEG before send. Headline-per-source preview is already in the Preview tab.

3. **More than one pool a day.** The pool mechanism exists; what is missing is fetching through the day and assembling a short morning and evening book from it.

4. **Gmail and Calendar on the daily run.** Code is ready; flags are still off. Needs Google OAuth files on the machine (`credentials.json` / `token.json`).

5. **Stock-Kindle navigation, not scripts.** Internal links, a better opening page, maybe clippings later. JavaScript, forms, and quizzes will not run on an unmodified Kindle — see `docs/research/2026-08-14-kindle-interactive-epub.md`.

6. **Kindle library cleanup is manual.** Amazon has no auto-delete for Send-to-Kindle personal documents. See [docs/research/2026-08-30-kindle-auto-delete.md](docs/research/2026-08-30-kindle-auto-delete.md).

## Later

- Fail-closed dashboard reads on a shared Mac (writes already need a token).
- Wordflow as its own product, or dropped. It is not part of the digest.

## Won't

- Interactive EPUB quizzes or in-book JavaScript on stock Kindle.
- Treating RSS URLs as untrusted-by-default (this is a personal digest; you pick the feeds).
