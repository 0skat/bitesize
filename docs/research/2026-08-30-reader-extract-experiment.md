# Reader-like extract experiment — trafilatura vs readability-lxml on the same GET

**Date:** 30 August 2026
**Scope:** Task 2 of `docs/superpowers/plans/2026-08-30-tags-reader-scoring.md`. Measures whether swapping or adding a Readability-class extractor (`readability-lxml`) on the *same* HTTP GET that `paywall.py` already performs improves the number of articles BiteSIze can read in full, without running a browser, executing page JavaScript, or touching login state.

## What was tested

`reader_extract.extract_article_text(html)` (new module) runs `readability-lxml`'s `Document(html).summary()` — the same family of algorithm as Firefox/Safari Reader's ancestor, but scored on the static HTML BiteSIze already downloads. This was compared against the existing `paywall._extract_text` (trafilatura) on identical bytes, for real articles.

No rendered-DOM / headless-browser path was measured. Per `docs/research/2026-08-30-safari-reader-paywall.md` §8 experiment 3, that is a separate, heavier experiment (seconds per article, a browser dependency) that only pays off if experiments 1–2 (same-bytes extractor swap, tested here) fail to close the gap. They didn't need to — see results.

## Method

`scripts/measure_reader_extract.py`: pulled up to 2 recent article URLs per RSS source, round-robining across the Brazil / Tech / World categories in `sources.json` so all three are represented, until ~20 unique URLs were collected. For each URL: one `feed._download_url` GET, then both extractors ran on those same bytes. "Usable" = at least `min_body_chars` (180) characters, same threshold `paywall.py` already uses to decide "direct fetch worked."

Sample: 22 URLs attempted (10 Brazil, 8 Tech, 4 World across G1, Folha, Agência Brasil, UOL, The Verge, Ars Technica, Wired, TechCrunch, BBC World, Al Jazeera, NPR — 1 URL, AP News, could not even be sampled because its RSS feed 403s at the network layer, unrelated to extraction).

## Results

| Category | Source | trafilatura chars | readability chars | Notes |
|---|---|---:|---:|---|
| Brazil | G1 - Globo | 3313 | 3315 | both usable |
| Brazil | G1 - Globo | 1075 | 1870 | both usable |
| Tech | The Verge | 1215 | 990 | both usable |
| Tech | The Verge | 1452 | 1223 | both usable |
| World | BBC World | 3473 | 3367 | both usable |
| World | BBC World | 5283 | 5101 | both usable |
| Brazil | Folha de S.Paulo | 1791 | 2018 | both usable |
| Brazil | Folha de S.Paulo | 6033 | 6358 | both usable |
| Tech | Ars Technica | 0 | 0 | **missing HTML**, not an extractor problem |
| Tech | Ars Technica | 0 | 0 | **missing HTML**, not an extractor problem |
| World | Al Jazeera | 397 | 52 | **trafilatura-only win** — video-caption page, readability picked a shorter node |
| World | Al Jazeera | 3558 | 3309 | both usable |
| Brazil | Agência Brasil | 3867 | 3796 | both usable |
| Brazil | Agência Brasil | 1601 | 1540 | both usable |
| Tech | Wired | 2367 | 2360 | both usable |
| Tech | Wired | 52415 | 51290 | both usable |
| Brazil | UOL Notícias | — | — | fetch failed (unrelated timeout) |
| Brazil | UOL Notícias (dup via Folha redirect) | 1791 | 2018 | both usable |
| Tech | TechCrunch | 6991 | 7062 | both usable |
| Tech | TechCrunch | 4917 | 4917 | both usable |
| World | NPR News | 3587 | 4117 | both usable |
| World | NPR News | 2692 | 2955 | both usable |

**Aggregate (21 URLs that actually fetched):**

- trafilatura usable: **19/21 (90.5%)**
- readability usable: **18/21 (85.7%)**
- both usable: 18/21
- readability-only wins (readability usable, trafilatura not): **0**
- trafilatura-only wins (trafilatura usable, readability not): **1** (Al Jazeera video-caption page)
- net readability vs trafilatura usable-count delta: **-5.3%**

The two Ars Technica misses returned 0 characters for *both* extractors — the GET itself came back without an article body (bot-blocked or empty response), confirming the research note's "missing HTML" case, which no static-HTML extractor (trafilatura, readability, or otherwise) can fix.

On the unit-test fixture built for this task (long `<article>` tag next to a short "assine agora" overlay paragraph), both extractors correctly picked the long article — semantic `<article>` markup is enough for trafilatura's own rules already, so readability had nothing extra to win there either. A second, more adversarial fixture (no `<article>` tag, teaser visually first, real body CSS-hidden via `display:none`, built during exploration but not committed) showed readability can also make things *worse*: it picked the teaser paragraph over the longer hidden block, because neither extractor renders CSS, and readability-lxml's link/text-density scoring isn't a strict superset of trafilatura's.

## Rule applied

Per the plan: **keep if readability gives ≥20% more usable full-text articles than the trafilatura baseline, or a clear win on overlay fixtures without making teasers worse.**

- Usable-count delta was **-5.3%**, not +20%.
- It produced **zero** net wins on real articles and **one** net loss (a usable trafilatura page became a teaser under readability).

## Decision: DROP

Swapping or adding readability-lxml as a second static-HTML extractor does not clear the bar. It doesn't recover any of the real missing-HTML failures (those are server-side, not extractor-side), and on the samples where both extractors had a full body to work with, it was a wash to slightly worse, with one real regression. This matches the research note's prediction: an extractor swap on the *same bytes* only changes which mistake is made; it cannot invent paragraphs the anonymous GET never received.

**`paywall.py`'s fetch order is unchanged.** `reader_extract.py` and its tests stay in the tree (documented, not deleted) so this measurement doesn't need to be re-run from scratch if a future experiment (e.g. a rendered-DOM pass, §8 experiment 3) wants a static-extract baseline to beat.

## What would change this

- A rendered-DOM experiment (headless browser, wait-for-idle, then extract) per §8 experiment 3 — this measures the *JavaScript* gap, which is a different question than "which static extractor is better," and wasn't run here.
- A larger, more overlay-specific sample (sites known to CSS-hide content) might surface cases readability wins; the 21-URL general sample here didn't happen to hit one.
