# Issues

Open problems seen in the running app. There is no GitHub issue tracker yet. Close an item here when it is no longer true.

## Antigravity flakes during the daily run

**Expected:** Filter, summaries, and covers come back from `agy`.  
**Actual:** Recent morning logs show `Antigravity exited 1` and `status 'ERROR'`. Articles are still kept (fallback scores). Some section covers and the global cover fall back to the non-AI layout.

Seen on 29–30 August 2026 in `output/logs/digest-stdout.log`. Hypothesis: timeout or model error on large batches, not a missing CLI (later calls in the same run succeed).

## AP News feed is dead

**Expected:** The World “AP News” source contributes headlines.  
**Actual:** `https://apnews.com/hub/apf-topnews?format=rss` yields zero articles. It previously logged `403 Forbidden`; as of 19 October 2026 it fails earlier, in the parser — `not well-formed (invalid token)` — so the URL is serving something that is not RSS at all.

**Now disabled in the dashboard** rather than left enabled to fail every morning. The other World feeds are unaffected. Re-enabling needs a current AP feed URL; the `apf-topnews` hub no longer appears to be one.

## Paywall mirrors almost never help

**Expected:** When the direct article fetch is thin, archive.is → 1ft.io → archive.org → removepaywall.com recover the text.  
**Actual:** Daily stats show archive.is, 1ft.io, and removepaywall at ~0%. archive.org sometimes recovers a batch (about 14/18 on 30 August). Overall full-text rate is still high because most articles succeed on the first request.

## Books toggle is a text box

**Expected:** `books_delivery_enabled` is a checkbox, like Kindle delivery and the Gmail/Calendar flags.  
**Actual:** The Settings tab renders it as a text field with the string `true`. The `books` group also has no friendly label (it shows as “books”).

Hypothesis: `BOOL_KEYS` and `GROUP_LABELS` in the dashboard script were not updated when the iCloud Books settings were added. Saving the word `true` may still work; saving anything else would not.

## Dashboard reads have no token

**Expected:** On a shared machine, settings are not readable by every local process.  
**Actual:** Write APIs require a Bearer token. `GET /api/settings` and `GET /api/sources` do not. SMTP password is masked on GET; everything else is plaintext on localhost.

This matches the documented single-user threat model. It is still an issue if the Mac is shared.

## Work is not on `main`, and there is no remote

**Expected:** The running digest is the published default branch.  
**Actual:** Useful work is on `main` at [github.com/victor-salles/bitesize](https://github.com/victor-salles/bitesize). Local feature worktrees may still exist; they are not the published default.

## Relevance scores pile up in the same edition

**Expected:** Stories in one digest have a useful spread, so “top stories” are actually the most important ones.  
**Actual (30 Aug 2026):** The most common on-page scores were **7.8, 7.0, and 6.2** — the old length-bucket fallback (78 / 70 / 62) when AI omitted scores or batches failed. That was not the model rating everything equal.

**Belief now:** The August pile was fallback clustering, not proof the AI cannot discriminate. Continuous fallback (capped below 70), tie-spread, and batch-comparative prompting already landed. Task 3 added `relevance_source` (`ai` vs `fallback`) so cover/top picks prefer real AI scores, plus one listwise title-rank pass per batch when AI scores are still too clustered (`unique/n < 0.35`).

**Still open:** Next morning digest should confirm the fallback layer no longer walls at 7.8; listwise un-clustering needs the same real-world check.

**Note:** listwise un-clustering is now skipped entirely when `user_interests` is set. Under interest scoring, clustered scores are real signal — a batch of twenty off-topic stories *should* all score low — and re-spreading them across the batch min/max would lift off-topic stories back over `min_keep_score`. The real-world check above therefore only applies to runs with no interests configured.

## README documents a "Jev triage" feature that is not in the code

**Expected:** README's Features list and its "Optional phases → Jev" section describe ad/relevance triage driven by "compiled relevance from your ranked themes", a `jev_triage_enabled` setting, a `jev_min_keep` threshold, a TypeSafe / Vercel AI Gateway key, a Jev dashboard tab, and runs logged under `output/jev/`.

**Actual:** There is no `jev` anywhere in the tree — no module, no settings key, no dashboard tab, no tests. `grep -ri jev --include='*.py'` returns nothing, and `SETTINGS_DEFAULTS` has no such keys.

Introduced by the README rewrite (PR #21). The described keep-threshold overlaps with `min_keep_score`, which does exist. Either the section should be removed or the feature should be built; until then a new operator will look for settings that are not there.

## Dashboard has no `claude` backend picker

**Expected:** Choosing an AI backend in Settings offers the backends `ai.py` actually routes to.

**Actual:** The Settings tab renders every setting generically from `/api/settings`, so `ai_backend` is a free-text box. It works — typing `claude` selects the new backend — but nothing tells you which values are valid, and a typo silently falls through to the Gemini backend (`ai.py` uses `else`, not a match on `gemini`).

Same root cause as the books-toggle issue: the dashboard has no per-key widget map beyond `BOOL_KEYS`.

## `_extract_json` prefers arrays over objects

**Expected:** `gemini._extract_json` recovers JSON of either shape from a model response.

**Actual:** When the direct `json.loads` fails, the regex fallback tries `\[[\s\S]*\]` **before** `\{[\s\S]*\}`. For the section- and global-cover prompts, which ask for an object containing a `top_stories` array, that returns the inner array and the caller rejects it with `Expected dict, got list` — every cover silently falls back to the non-AI layout.

Only reachable when the direct parse fails, i.e. when the model wraps its reply in a markdown fence. The Claude backend strips a wrapping fence before returning (`claude_backend._strip_code_fence`) so the direct parse wins; the docstring claims fence tolerance that the function does not actually implement. A backend-agnostic fix would try the object pattern first, or strip fences inside `_extract_json`.

## Closed here on purpose (do not re-open from old plans)

These were open in `docs/superpowers/plans/2026-05-26-open-source-security-readiness.md`. The code has moved on:

- Gmail/Calendar are wired into `main.py` (flags still off — that is a roadmap item, not a bug).
- Dashboard writes send `Authorization: Bearer`.
- `dashboard.py` calls `load_env()` on import and always has a write token.
- Partial AI batch JSON no longer drops missing article ids.
- Google OAuth uses combined scopes; calendar “today” uses local time.
- `--dangerously-skip-permissions` is not in the current Antigravity backend.
