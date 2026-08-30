# Safari Reader vs BiteSIze fetch — research note

**Date:** 30 August 2026  
**Scope:** Personal digest. BiteSIze downloads article URLs with `requests`, extracts text with trafilatura, then tries archive mirrors. iPhone Safari Reader often shows a full story when that pipeline only keeps a teaser.  
**Method:** First-party Apple/WebKit docs, WebKit source comments, and one academic paper that describes Safari Reader internals. Uncertain facts are marked. This note is about **why a rendered browser page yields more text than a raw GET**. It is not a guide to stealing paywalled work.

**How to read this:** Reader is not a secret unlock. It reads the page *after* Safari has loaded it like a person. We never do that step.

---

## Bottom line

Safari Reader runs on a **finished, laid-out page**. Apple has said Reader exists since 2010 and strips navigation so the article is “formatted for easy reading and presented all on one page.” ([WebKit, Safari 18.1](https://webkit.org/blog/16188/webkit-features-in-safari-18-1/))

A Brave research paper that measured Reader implementations describes Safari Reader as a JavaScript library descended from Arc90 Readability. Unlike tools that work on the first HTML bytes, Safari Reader **must load the page and at least some CSS/JS** because it uses **on-screen layout** (where blocks sit, what is hidden) to pick the main column. ([Gugelmann et al., SpeedReader, arXiv:1811.03661](https://arxiv.org/abs/1811.03661))

BiteSIze never lays the page out. It GETs bytes and asks trafilatura for text. If the first response is a lede plus “subscribe,” that is all we have — unless an archive mirror has a fuller snapshot.

---

## What Reader is (and is not)

| Claim | Source | Certainty |
|---|---|---|
| Reader is a Safari feature (Mac, iPhone, iPad) for article pages, since 2010 | [WebKit blog, Safari 18.1](https://webkit.org/blog/16188/webkit-features-in-safari-18-1/) | High |
| Safari 18.1 can summarize that Reader article with Apple Intelligence | same | High |
| Apps can open a URL in Safari’s UI and **enter Reader if available** | [`SFSafariViewController.Configuration.entersReaderIfAvailable`](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller/configuration/entersreaderifavailable) | High |
| `WKWebView` has a **public** “give me Reader HTML” API | — | **No such API found.** Apple’s documented path is Safari / `SFSafariViewController`, which is a browser sheet, not a text-extract function. |
| Apple publishes the scoring algorithm | — | **No.** The open cousin is [mozilla/readability](https://github.com/mozilla/readability) (Firefox). Treat it as a cousin, not as Safari. |

`entersReaderIfAvailable` is a boolean on the Safari view configuration: enter Reader automatically when Safari thinks the page is an article. Default is false. It does not return the article string to your code. ([Apple documentation](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller/configuration/entersreaderifavailable))

---

## Why Reader “beats the paywall” on many sites

Two different publisher tricks get lumped together as “paywall”:

1. **Overlay.** The full article is already in the HTML. A box or blur sits on top. Safari has rendered the page; Reader picks the dense text column and **drops the overlay**. The paper above says Safari uses “what elements are hidden from display” when it scores blocks. Uncertain how often today’s sites still leave the full text in the DOM — many do; some do not.

2. **Teaser only.** The first HTML (what our GET sees) really is a *resumo*. The rest arrives after login, a meter cookie, or a late script. Safari on the iPhone often **already has those cookies** from earlier reading, and it **runs the scripts**. Our fetch is anonymous and scriptless, so we stay on the teaser.

3. **Hard wall.** The full sentences are never in the document. Reader then shows the same short *resumo* we do, or refuses to offer Reader at all.

So the iPhone “success” is usually: **same URL, richer document after render + session**, then a main-content extract. It is not that Reader has a better archive.is.

---

## What BiteSIze does today

```
GET article URL (no browser, no cookies)
  → trafilatura extract
  → if too short: GET archive.is / 1ft.io / archive.org / removepaywall
```

Daily logs already show the first three mirrors near 0% and archive.org only sometimes useful. That matches “teaser in the live HTML, and the mirrors do not have a fuller copy.”

---

## Experiments worth trying (personal Mac, not a product claim)

1. **Detect *resumo* vs *artigo-completo*** in the pipeline we already have (length, subscribe language, AI tag). That is roadmap item 1 — do this first. It does not need Safari.
2. **Readability on the HTML we already downloaded.** Cheap. Helps only when the full text was in that HTML (overlay case). Mozilla’s library is the documented open extract; it is not Safari.
3. **A real render** (headless WebKit/Chromium, or a local Safari automation) then extract. This is the only experiment that copies the “run JS, then pick the column” step. Slow; only for stories tagged *resumo*.
4. **Do not** treat `SFSafariViewController` as a fetch backend. It is a human-facing Safari sheet. There is no supported “return Reader text to Python” API.

---

## Source list

| Source | Role |
|---|---|
| [WebKit — Safari 18.1](https://webkit.org/blog/16188/webkit-features-in-safari-18-1/) | Official: what Reader is, since 2010, summaries |
| [Apple — `entersReaderIfAvailable`](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller/configuration/entersreaderifavailable) | Official: enter Reader in Safari’s in-app browser |
| [SpeedReader, arXiv:1811.03661](https://arxiv.org/abs/1811.03661) | Academic description of Safari Reader as post-render, layout-aware |
| [mozilla/readability](https://github.com/mozilla/readability) | Open cousin (Firefox), not Apple’s code |
