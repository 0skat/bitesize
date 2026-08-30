# Why digest scores look the same — research note

**Date:** 30 August 2026  
**Question:** Why do most stories in one BiteSIze edition get the same or very similar relevance scores, and what actually improves ranking?  
**Method:** Code + the 30 August EPUB histogram, plus a wave of primary/peer-reviewed sources on LLM-as-judge and IR ranking. Material claims have at least two sources unless marked `[single-source]`.

## TL;DR

Two different failures got mixed together.

1. **The August 30 book** piled up at 7.8 / 7.0 / 6.2 because the old fallback mapped *length* to five fixed numbers. That is not “the AI thought they were equal.” When Antigravity failed, long articles all got 78. Length is a bad proxy for news importance. [^1][^2][^3]
2. **Even when the model answers**, pointwise 0–100 scores compress toward the middle/high band. Judges avoid extremes, overrate, and emit a handful of integers — so many stories look like 7-ish. Prompting “use the full scale” helps less than forcing a *relative order*. [^4][^5][^6]

What already landed (do not revert): fallback is continuous and stays below 70; ties get a recency spread; the batch prompt asks for unique, comparative scores.

What is still worth building: a **second pass that ranks titles relative to each other** when a batch’s scores are still too clustered, and **keep fallback scores out of “top stories.”** Pairwise-all-pairs is better in papers and too expensive for 120 articles. [^6][^7][^8]

## What we measured in the product

In the 30 August 2026 EPUB the most common on-page scores were exactly 7.8, 7.0, and 6.2 — the old length buckets (78 / 70 / 62). Thirty-three items sat at 7.8. Sort among them was title A–Z. Same-day logs show Antigravity errors on some batches.

That histogram is **fallback clustering**, not proof the model cannot discriminate. The next morning run (after the fallback change) is the test of that layer.

## Finding 1 — Length is not importance

IR has treated raw length as a bias to *correct*, not a quality signal: longer documents collect more term hits; BM25 and later work normalize length. [^1][^2] Journalism work finds news factors predict length and placement only loosely — influence and continuity often do not. Short wire briefs can be the day’s most important item. [^3][^9]

BiteSIze’s old fallback did the opposite: longer body → higher “relevance.” After a full-text fetch, most stories are long, so they share one bucket.

## Finding 2 — Pointwise LLM scores cluster even when the model is up

LLM judges show **central tendency** and **leniency**: mid-scale compression, high scores for mediocre items, rare use of the bottom of the scale. [^4][^5] Discrete integer output collapses small differences into the same label. [^10] Isolated (pointwise) ratings lack the other items as context, so the scale drifts. [^6][^11]

For news/IR labels specifically, judges systematically **overrate** passages versus humans and default to ties when gaps are subtle. `[single-source]` [^12]

This matches the user’s *feeling* on editions where the AI *did* respond: many 6–8s, few 2s or 9s. The prompt already says “at most one in five above 80.” Papers treat that kind of quota as weakly evidenced; **relative ranking** is the better-supported fix. [^8][^13]

## Finding 3 — Relative order beats a better 0–100

On IR benchmarks, listwise permutation (RankGPT) and pairwise prompting beat independent yes/no or Likert scores. Pointwise is cheap and ties; pairwise is accurate and O(n²); listwise sits in between. [^6][^7][^8] Fine-grained pointwise (many bins) narrows the gap but News is a subset where listwise still wins. [^14]

You can keep a 0–10 display by mapping **rank position** to a score after a listwise pass (rank 1 of N → high, last → low). Post-hoc z-score of already-clustered Likert numbers only stretches noise. [^15]

## What to change in BiteSIze (justified)

| Change | Why | Cost |
|--------|-----|------|
| Keep current fallback cap + tie-spread | Fixes the August 30 pile; length must not own the top of the book | Done |
| Mark `relevance_source`: `ai` vs `fallback` | Cover / top picks should not treat a length stand-in as a 7.8 | Small |
| When a processed batch has few unique AI scores (e.g. unique/n < 0.35), one extra **listwise title rank** and remap scores from that order | Same evidence as RankGPT; one call per clustered batch, not 120×119 pairs | One extra AI call |
| Do not revert to five length buckets | Literature + our histogram | — |

Do **not** implement full pairwise on the daily 120-article run. Do **not** z-score the whole edition just to make the Kindle look more varied.

*Implemented 30 Aug 2026 (task 3): `relevance_source`, listwise un-cluster pass, cover ranking prefers AI scores.*

## Gaps

- Little evidence on pt-BR prompts and Antigravity/Gemini for *news importance* (not query relevance).
- No second morning EPUB yet under the new fallback.
- Forced-distribution prompt quotas lack a clean ablation. [^13]

## Sources

[^1]: Robertson & Walker, SIGIR 1994 — length in probabilistic retrieval: https://www.staff.city.ac.uk/~sbrp622/papers/robertson_walker_sigir94.pdf
[^2]: Singhal, Buckley & Mitra, SIGIR 1996 — pivoted length normalization: https://dl.acm.org/doi/10.1145/243199.243206
[^3]: Boukes, Jones & Vliegenthart, *Journalism* 2022 — news factors vs length/prominence: https://doi.org/10.1177/1464884919899313
[^4]: Central tendency in LLM raters: https://arxiv.org/pdf/2605.16386
[^5]: Judge calibration / mid-scale compression: https://arxiv.org/html/2605.09227
[^6]: Zheng et al., MT-Bench / LLM-as-judge: https://arxiv.org/abs/2306.05685
[^7]: Sun et al., RankGPT: https://arxiv.org/abs/2304.09542
[^8]: Qin et al., Pairwise Ranking Prompting, NAACL 2024: https://aclanthology.org/2024.findings-naacl.97
[^9]: Google Search ranking systems (not word-count as quality): https://developers.google.com/search/docs/appearance/ranking-systems-guide
[^10]: TrustJudge — discrete score information loss: https://arxiv.org/abs/2509.21117
[^11]: Pairwise vs pointwise feedback protocols: https://arxiv.org/pdf/2504.14716
[^12]: LLM judges overrate IR relevance: https://arxiv.org/html/2602.17170
[^13]: LLM-as-judge practice notes (rubrics / quotas): https://zeroentropy.dev/concepts/llm-as-judge/ `[single-source]`
[^14]: Likert-or-not, fine-grained pointwise vs listwise: https://doi.org/10.48550/arxiv.2505.19334
[^15]: OpenSearch z-score for *hybrid retrieval fusion*, not LLM news scores: https://opensearch.org/blog/introducing-the-z-score-normalization-technique-for-hybrid-search/
