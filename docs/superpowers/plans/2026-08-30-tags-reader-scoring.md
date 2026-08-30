# Tags, Reader extract, and scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Label every story as resumo vs artigo-completo plus pt-BR topics; try a Reader-like extract, measure it, and keep or drop it; investigate why relevance scores cluster and improve ranking if the evidence supports a change.

**Architecture:** Three isolated workstreams. Tags live in a small `tags.py` plus the existing AI batch JSON. Reader extract is a new fetch adapter behind `paywall.py`, measured before it becomes the default. Scoring research writes a note first; code changes only what that note justifies.

**Tech Stack:** Python 3.13, pytest, existing Antigravity/Gemini/Ollama router, trafilatura, optional Mozilla Readability (via a thin subprocess or `readability-lxml` if already usable). No new paid APIs.

## Global Constraints

- Tag vocabulary is **pt-BR only**. Tipo is exactly `resumo` or `artigo-completo`. Temas may only be: `política`, `saúde`, `economia`, `tecnologia`, `mundo`, `brasil`, `cultura`, `esportes`, `ciência`, `opinião`, `clima`.
- RSS categories (Brazil / Tech / World) stay the EPUB spine. Tags are extra metadata, not new sections.
- Do not invent English topic labels. Do not add themes outside the list.
- Heuristic completeness (short body, RSS-snippet match, subscribe/paywall language) must run in code even when the AI is down.
- Show tags on the article page in the EPUB (pt-BR labels via `ai_locale.py`).
- Reader work is **not** a circumvention guide. No `SFSafariViewController` as a fetch backend. No logged-in cookie theft. Anonymous GET + optional headless render + extract only.
- Reader path must be measured on a real sample before it becomes default. Write keep/drop and the numbers in `docs/research/2026-08-30-reader-extract-experiment.md`.
- TDD: failing test first for every behavior change. `pytest tests/ -v` green before commit.
- Never commit `.env`, `data/`, `token.json`, `credentials.json`, or `output/`.
- Commit with `git commit -m` only. No `--trailer`, no Cursor attribution.
- Task 1 must not change the HTTP fetch stack. Task 2 must not change the AI JSON schema or tag vocabulary. Task 3 must not add tags or a new fetch backend.
- Work from the assigned worktree only.

---

## File map

| File | Responsibility |
|------|----------------|
| `tags.py` | Vocabulary, heuristic tipo, normalize AI tags |
| `gemini.py` | Extend batch JSON with `tipo` + `temas`; scoring prompt/calibration (Task 3 only) |
| `ai_locale.py` | pt-BR / en labels for tipo, temas, tag line |
| `epub.py` | Render tag line on article pages |
| `reader_extract.py` | Readability / rendered-DOM extract (Task 2) |
| `paywall.py` | Call reader extract only if Task 2 keeps it |
| `tests/test_tags.py` | Tag heuristics + normalize |
| `tests/test_reader_extract.py` | Extract behavior |
| `docs/research/2026-08-30-reader-extract-experiment.md` | Measurement + keep/drop |
| `docs/research/2026-08-30-relevance-scoring.md` | Scoring deep-research |

---

## Task 1: Tag system (pt-BR tipo + temas)

**Worktree:** `.worktrees/tags-ptbr`  
**What:** Every kept article gets `tipo` and `temas`. Heuristics first; AI fills/overrides in the same batch that already does skip/summary/relevance. EPUB shows the tags.

**Steps:**

- [ ] Write failing tests in `tests/test_tags.py`: short/subscribe text → `resumo`; long unique body → `artigo-completo`; unknown tema dropped; AI `tipo` invalid falls back to heuristic.
- [ ] Run tests — confirm they fail for missing `tags` module.
- [ ] Implement `tags.py` with `TIPOS`, `TEMAS`, `infer_tipo(art)`, `normalize_tags(art, ai_item=None)`.
- [ ] Heuristics: body shorter than `min_body_chars` → `resumo`; body nearly equal to RSS/title snippet → `resumo`; regex for assine/subscribe/paywall/continue reading → `resumo`.
- [ ] Extend `process_articles` JSON: each object may include `"tipo"` and `"temas":["política"]`. Apply `normalize_tags` after parse and on fallback (no AI).
- [ ] Prompt: require tipo + temas from the fixed lists; do not invent labels.
- [ ] Add EPUB labels and a one-line tag display under the summary meta (tipo, then temas joined).
- [ ] Tests for AI batch wiring (mock `_call_ai` like `test_gemini_batch.py`).
- [ ] `pytest tests/ -v` green. Commit.

**Done when:** A mocked batch stores `tipo`/`temas` on articles; heuristics work with AI off; EPUB HTML includes the pt-BR tag line; no fetch-stack changes.

---

## Task 2: Reader-like extract — experiment, measure, keep or drop

**Worktree:** `.worktrees/reader-extract`  
**What:** Follow `docs/research/2026-08-30-safari-reader-paywall.md` §8. Compare current GET+trafilatura vs Readability-on-same-bytes vs (optional) rendered-DOM extract. Keep the winner only if it beats the baseline on a written metric.

**Steps:**

- [ ] Read the research note end-to-end. Do not use SFSafariViewController. Do not steal login cookies.
- [ ] Write failing tests for a `reader_extract.extract_article_text(html: bytes) -> str` that, given fixture HTML with a long `<article>` plus a short subscribe overlay, returns the long article (current trafilatura-on-that-fixture is the baseline to beat or match).
- [ ] Implement extract: prefer a Readability-class pass on already-downloaded HTML (`readability-lxml` or equivalent small dependency — add to `requirements.txt` only if tests need it and you keep the path).
- [ ] Build `scripts/measure_reader_extract.py`: 15–25 URLs from enabled Brazil/Tech/World feeds (or recent digest links if present). For each URL record: direct trafilatura chars, Readability-on-same-GET chars, usable? (`min_body_chars`), and if cheap/available, rendered-DOM chars. No full daily digest.
- [ ] Run the script. Write `docs/research/2026-08-30-reader-extract-experiment.md` with the table, the rule used (keep if ≥20% more usable full-text articles than baseline, or clear win on overlay fixtures without making teasers worse), and **KEEP** or **DROP**.
- [ ] If KEEP: wire the winning extract into `paywall.fetch_with_paywall_bypass` after the direct GET, before mirrors. If DROP: leave `paywall.py` fetch order unchanged; keep `reader_extract.py` + tests + the experiment note so the decision is documented.
- [ ] `pytest tests/ -v` green. Commit.

**Done when:** Experiment note exists with numbers and KEEP/DROP; tests cover the extract function; paywall default only changes on KEEP.

---

## Task 3: Relevance scoring — deep research, then justified code

**Worktree:** `.worktrees/scoring-research` (code only after the research note exists)  
**What:** The user sees most stories in one edition with the same or very similar scores. Investigate *why* (code + literature). Recommend improvements. Implement only what the note supports.

**Already in tree (do not revert):** `_fallback_relevance` is continuous and capped below 70; `spread_tied_scores` breaks ties; the AI prompt asks for a batch-relative full scale. The 30 Aug book still showed 7.8/7.0/6.2 piles from the *old* fallback. Research must say what remains after that change.

**Steps:**

- [ ] Deep-research (controller + low-tier workers): why LLM relevance scores cluster; news ranking / listwise vs pointwise; calibration and forced spread; length-as-proxy failure. Write `docs/research/2026-08-30-relevance-scoring.md` with citations.
- [ ] Compare findings to `gemini.py` (`process_articles`, `_fallback_relevance`, `spread_tied_scores`) and the Aug 30 EPUB score histogram in `ISSUES.md`.
- [ ] If the note names a concrete, testable improvement (e.g. two-pass rank of titles, discard fallback from “top stories”, require unique ranks in-batch), TDD it in `tests/test_relevance_ranking.py`.
- [ ] If the note says wait for the next morning digest, document that in `ISSUES.md` and do not churn the scorer.
- [ ] `pytest tests/ -v` green. Commit the note and any justified code.

**Done when:** Research note exists; ISSUES.md reflects current belief; code changes (if any) have tests and do not reintroduce the five-bucket fallback.
