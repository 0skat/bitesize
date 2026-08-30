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

The dashboard **Preview** tab now loads live headlines per source. Still missing: last-digest preview, AI summary preview, magazine cover preview.

## Next

1. **Tags in Portuguese: resumo vs artigo-completo, plus topics.** Most fetches are the teaser the site gives a robot — a *resumo* — not the *artigo-completo*. The digest treats them as the same. Add a tag system (labels in **pt-BR**) and put it in the same AI pass that already filters, summarizes, and scores.

   **Tipo (completeness)** — every story gets exactly one:
   - `resumo` — paywall teaser, lede-only, or “assine para continuar”
   - `artigo-completo` — enough body to read as the full piece

   **Temas** — zero or more, from a fixed list the model must use (it may not invent English labels):
   - `política` · `saúde` · `economia` · `tecnologia` · `mundo` · `brasil` · `cultura` · `esportes` · `ciência` · `opinião` · `clima`

   Also flag completeness in code when the text is short, matches the RSS snippet, or contains subscribe/paywall language — do not wait for the model alone. Show the tags on the article page and let a later pass group or filter by them. RSS categories (Brazil / Tech / World) stay as the spine; tags are extra.

2. **Learn from iPhone Safari Reader.** Reader often shows the full story when our fetch only gets the teaser. That is not a magic paywall key: Safari loads the page like a person (JavaScript, cookies, layout), then extracts the main column and ignores overlays. We do a raw download and strip text, so we only see what the first HTML already contains. Research note: [docs/research/2026-08-30-safari-reader-paywall.md](docs/research/2026-08-30-safari-reader-paywall.md). Next: try a Reader-like extract on a rendered page (not a new archive mirror), and be honest about sites that never put the full text in the document.

3. **A smaller morning book.** Daily runs land 120–140 articles. Relevance sorting exists; a tighter keep-list or a “top stories only” EPUB would make the Kindle actually readable.

4. **Dashboard previews (still open).** Last digest, a sample AI summary, and the cover JPEG before send. Headline-per-source preview is already in the Preview tab.

5. **Hourly pool, two builds a day.** Fetch through the day; assemble a short morning book and a short evening book. Mentioned as the next plan, not written yet.

6. **Gmail and Calendar on the daily run.** Code is ready; flags are still off. Needs Google OAuth files on the machine (`credentials.json` / `token.json`).

7. **Stock-Kindle navigation, not scripts.** Internal links, a better opening page, maybe clippings later. JavaScript, forms, and quizzes will not run on an unmodified Kindle — see `docs/research/2026-08-14-kindle-interactive-epub.md`.

## Later

- Dependabot and a public GitHub repo (the pre-publish checklist in README).
- Fail-closed dashboard reads on a shared Mac (writes already need a token).
- Wordflow as its own product, or dropped. It is not part of the digest.

## Won't

- Interactive EPUB quizzes or in-book JavaScript on stock Kindle.
- Treating RSS URLs as untrusted-by-default (this is a personal digest; you pick the feeds).
