# Safari Reader vs BiteSIze HTTP fetch — research note

**Date:** 30 August 2026  
**Scope:** Personal project (BiteSIze fetches article HTML with a plain HTTP GET, then extracts text with trafilatura, then tries archive mirrors). This note explains why iPhone / Safari **Reader** often shows a full article when that pipeline only gets a teaser.  
**Method:** Primary sources only. Apple Support, Apple Developer Documentation, WWDC transcripts, WebKit.org, WebKit source / bugs / changesets, Apple Developer Forums posts from Apple staff, the Brave SpeedReader paper (arXiv 1811.03661) where it cites Safari Reader internals, Mozilla Readability as the **open cousin** (not Safari). Uncertain facts are marked as such. This note does **not** describe jailbreaks, exploits, or how to take paywalled content without a subscription. The useful question is: **why a fully loaded, rendered browser page can contain more article text than a raw HTTP GET.**

**How to read this:** Safari Reader is a **after-the-page-loads** cleanup of a page the browser has already fetched, scripted, and laid out. BiteSIze never does that step. Copying “Reader” is not a hidden Apple API you can call from Python. The honest options are: run a real browser (or something that executes JavaScript), then extract from the resulting DOM (Mozilla Readability is the documented cousin); keep archive mirrors for pages whose server never sent the body; or accept teasers.

---

## Decision-relevant finding

Safari Reader does **not** fetch a secret full-text URL. Apple documents it as a reading view that appears **after you are already on a webpage**, and only when Safari decides that page “has an article.” ([Safari on Mac](https://support.apple.com/guide/safari/hide-ads-when-reading-sfri32632/mac), [Safari on iPhone](https://support.apple.com/guide/iphone/hide-ads-and-distractions-iphdc30e3b86/ios))

Researchers who compared reader engines (Brave, 2018) describe Safari Reader as a JavaScript library, descended from the same Arc90 “Readability” line as Firefox, but **changed to use layout and visibility**: where blocks sit on the page, and what is hidden from display. That means Safari must **load the page and at least some CSS/JS** before it can decide what is the article or build the Reader view. They contrast this with Mozilla Readability.js, which can score a DOM **without** render info (though Firefox still waits to *offer* Reader until the page has loaded). ([SpeedReader, arXiv 1811.03661, §2.2](https://arxiv.org/abs/1811.03661), [PDF](https://arxiv.org/pdf/1811.03661))

BiteSIze’s path is the opposite: `requests.get` bytes, then `trafilatura.extract` on that HTML, then the same extract on archive-mirror HTML. Trafilatura’s own docs say `extract` runs on **raw documents or already-parsed HTML trees**, with a rule-based extractor and fallbacks (including a Readability port). It does not load the page in a browser or run the site’s scripts. ([Trafilatura Python usage](https://trafilatura.readthedocs.io/en/latest/usage-python.html), BiteSIze `feed.py` / `paywall.py`)

So when Reader “has the story” and BiteSIze “has a teaser,” the usual explanation is **not** a better magic parser. It is that **the document Reader sees is a later document**: scripts have run, more nodes may exist, overlays may hide chrome without deleting the article from the tree, and cookies / a logged-in Safari session may have caused the **server** to send a longer first response than an anonymous GET.

There is **no public Apple API that returns Reader’s extracted article text**. `WKWebView`’s documented API loads and renders pages and can run JavaScript you supply; it does not list Reader. `SFSafariViewController` **can** show Safari’s Reader UI, but Apple says the app **cannot see** interactions with that web interface or website data. ([WKWebView](https://developer.apple.com/documentation/webkit/wkwebview), [SFSafariViewController](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller))

---

## 1. What Safari Reader is

Apple’s user guides:

- **iPhone:** “Use Reader to hide navigation menus and other distracting items.” “Reader formats a webpage to show just the relevant text and images.” It is available on a **supported** website via the page menu (**Show Reader**). You can turn on “Use Reader Automatically” per site, or for all sites under Settings → Apps → Safari → Reader. Longer pages can include a summary and table of contents. ([iPhone User Guide](https://support.apple.com/guide/iphone/hide-ads-and-distractions-iphdc30e3b86/ios))
- **Mac:** “You can use Safari Reader to view a webpage article in one page, formatted for easy reading and presented without navigation or other distractions.” You first **go to a webpage**, then Show Reader. **“The button appears only if the webpage has an article that Reader can show.”** ([Safari User Guide](https://support.apple.com/guide/safari/hide-ads-when-reading-sfri32632/mac))

WebKit.org (Safari 18.1 release notes): Safari Reader has existed **since 2010**; it shows articles “without navigation or other distractions,” formatted for reading, “presented all on one page,” with theme/font/size controls. Safari 18.0 refreshed the design; 18.1 added optional Apple Intelligence **Summarize** on that already-extracted article. ([WebKit Features in Safari 18.1](https://webkit.org/blog/16188/webkit-features-in-safari-18-1/))

WebKit.org (Safari 18.0): authors should use **semantic HTML** (`article`, `main`, and similar) so **Safari Reader** (and Safari Viewer) work better. That is a hint that Reader looks at document structure, not a published algorithm. ([WebKit Features in Safari 18.0](https://webkit.org/blog/15865/webkit-features-in-safari-18-0/))

**Uncertain:** Apple does not publish the scoring rules, which CSS properties count as “hidden,” or how much of the article must be in the first HTML vs filled in later by script. The 2018 Brave paper is a research snapshot of Safari Reader **as of that paper**, not a live spec.

Reader is **not** the same as later **Distraction Control** (manually hide banners). Apple points people who want a reading view back to Reader. ([Distraction Control](https://support.apple.com/120682))

---

## 2. Reader runs after the page is loaded and rendered

Several independent primary sources agree on the **timing**, even though they do not publish the extract code:

| Source | What it says about timing |
|---|---|
| Apple Support (Mac) | You navigate to the webpage first; the Reader control appears only if that page has an article Reader can show. ([sfri32632](https://support.apple.com/guide/safari/hide-ads-when-reading-sfri32632/mac)) |
| Brave SpeedReader paper | Existing major-browser reader modes (including Safari) are applied **after** the document is fully fetched and rendered. Safari Reader in particular **must** load the page and some resources to classify and extract, because it uses **on-screen position** and **hidden-by-default** checks. SpeedReader is proposed as the opposite: classify on **initial HTML** *before* subresources. ([arXiv 1811.03661](https://arxiv.org/abs/1811.03661) §2.2–2.3) |
| WebKit changeset (watchOS Reader) | Safari can detect that a **Reader version is available** while the **original page** is still running script; the Reader view is a **separate page load** that shares process/cache with the original so the user can leave Reader without re-fetching the site. Heavy script on the original page can delay Reader’s first paint. ([changeset 233891](https://trac.webkit.org/changeset/233891/webkit)) |
| WebKit bug (headings) | Reader’s output depends on heading/link patterns in the page as Safari sees them; changing markup changes what Reader keeps. That is post-DOM heuristic behavior, not a separate full-text API. ([Bug 225609](https://bugs.webkit.org/show_bug.cgi?id=225609)) |

The HTML standard’s script processing model is why a **rendered** page can differ from the first response body: the browser parses HTML, then **fetches and runs** classic and module scripts as part of loading the document. A client that only stores `response.content` never takes that step. ([HTML living standard — script processing](https://html.spec.whatwg.org/multipage/scripting.html#script-processing-model))

**Uncertain:** How long current Safari waits (DOMContentLoaded vs a quiet network vs a site-specific delay) before enabling the Reader button. Apple does not document a timeout.

---

## 3. Two different “paywall” situations (no circumvention)

From the **browser vs GET** gap, there are two honest cases. This is about **what is in the document**, not about how to remove a paywall.

### Overlay / hide-in-place (CSS or a covering layer)

The first HTTP response may already contain most of the article in the HTML tree. Scripts and stylesheets then cover it, dim it, or set `display: none` / similar on a block. CSS `display: none` generates no box; the element can still exist in the document tree. ([CSS 2.2, `display`](https://www.w3.org/TR/CSS22/visuren.html#display-prop))

A Reader engine that walks the **rendered** tree and **ignores nodes treated as hidden** (Brave’s description of Safari Reader) or that picks the densest **visible** text run can keep the article and drop the covering chrome. A GET + trafilatura pass might instead:

- pick the short “subscribe” paragraph as the “main” text, or
- stop at a teaser because the extractor’s density / boilerplate rules prefer the visible marketing block,

even when a longer article string is sitting elsewhere in the same bytes.

Safari Reader, per the 2018 paper, **explicitly** uses “what elements are hidden from display by default.” ([arXiv 1811.03661 §2.2](https://arxiv.org/pdf/1811.03661))

### Missing HTML (server never sent the body)

The GET that BiteSIze performs (anonymous `User-Agent`, no Safari cookie jar, no login) can receive a **short** HTML document: headline, dek, paywall copy, and no article nodes. No extractor—Reader, Readability, or trafilatura—can invent paragraphs that are not in the tree.

A **rendered Safari session** can still show a long article when:

- the reader is **signed in** and the **HTML response itself** is longer (cookies / session), or
- scripts **request** more HTML or JSON after load and **insert** it into the DOM.

The first is a **different HTTP response**, not a smarter parser. The second is **JavaScript after parse**, which BiteSIze does not run. ([HTML script processing](https://html.spec.whatwg.org/multipage/scripting.html#script-processing-model), [WKWebView loads request then embedded resources and renders](https://developer.apple.com/documentation/webkit/wkwebview))

**Uncertain / do not assume:** That “Safari showed the article” means the site put the full story in the first GET for everyone. Compare **Save Page Source** (or the Network panel’s document) with Reader before treating a site as overlay-only.

Archive mirrors (what BiteSIze already tries) only help if **some crawler, in the past, stored a richer HTML snapshot**. They do not recreate a live logged-in Safari tab.

---

## 4. What BiteSIze does today

Inspected in-repo, 30 August 2026:

1. **`feed._download_url`** — `requests.get` with timeout, a configured `User-Agent`, certifi TLS, redirects. Returns **raw bytes**. No browser, no JavaScript. (`feed.py`)
2. **`paywall._extract_text`** — `trafilatura.extract` on those bytes (`no_fallback=False`, comments/tables off). Trafilatura documents `extract` as main-text extraction on a raw document or lxml tree, with a cascade (own rules, then readability / jusText if the first pass is short). ([Trafilatura](https://trafilatura.readthedocs.io/en/latest/usage-python.html))
3. **Usable length** — if extracted text is shorter than `min_body_chars`, treat the direct fetch as a miss.
4. **Mirrors** — same GET + extract against archive.is, 1ft.io, archive.org, removepaywall.com (`paywall.py`). Stats go to `output/logs/paywall-stats.log`.

That stack is a good **static HTML** reader. It is not Safari Reader.

Trafilatura even ports Mozilla’s `is_probably_readerable` helper. That is the **cousin** algorithm on **the same bytes BiteSIze already has**, not Apple’s Reader. ([Trafilatura — guessing if text can be found](https://trafilatura.readthedocs.io/en/latest/usage-python.html))

---

## 5. Mozilla Readability — open cousin, not Safari

[mozilla/readability](https://github.com/mozilla/readability) is “a standalone version of the readability library used for [Firefox Reader View](https://support.mozilla.org/kb/firefox-reader-view-clutter-free-web-pages).” License header: Arc90 (2010), Apache 2.0.

You give it a **DOM `document`**, then `parse()`. It returns title, HTML `content`, `textContent`, and metadata. It **mutates** the DOM unless you clone first. In Node it typically uses jsdom; Mozilla **strongly recommends leaving script execution off**. `isProbablyReaderable` is a cheap pre-check. ([README](https://github.com/mozilla/readability/blob/main/README.md))

The SpeedReader paper: Readability.js scores **text and link density** and does **not** use display/presentation, so it **can** run on HTML that was never laid out. Safari Reader is a **fork of the same ancestor** with **added render heuristics**. They are relatives, not the same engine. ([arXiv 1811.03661 §2.2](https://arxiv.org/pdf/1811.03661))

**Implication for BiteSIze:** swapping trafilatura for Readability on the **same GET** may change teaser-vs-boilerplate mistakes. It will **not** add paragraphs that only appear after JavaScript. To approximate Safari’s *inputs*, you need a **loaded DOM** (browser or a JS-enabled runtime), then Readability (cousin) or trafilatura on `document.documentElement.outerHTML`.

---

## 6. Apple APIs: what you can and cannot call

### No public extract algorithm

Apple’s developer documentation for embedding the web describes **views**, not “give me Reader’s article string.” WebKit.org tells **site authors** to use semantic HTML so Reader works; it does not ship the classifier. ([Safari 18.0](https://webkit.org/blog/15865/webkit-features-in-safari-18-0/), [WKWebView](https://developer.apple.com/documentation/webkit/wkwebview), [SFSafariViewController](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller))

Open WebKit has **other** text-extraction machinery (`TextExtraction`, SPI such as `_requestTextExtraction`) aimed at **visible text for system services**, not documented as Safari Reader. ([WebKit PR 23317](https://github.com/WebKit/WebKit/pull/23317)) WebKit bugs and changesets discuss **Reader mode in Safari** as a **Safari client** feature that can break when loader/policy code changes ([Bug 182697](https://bugs.webkit.org/show_bug.cgi?id=182697), [changeset 228430](https://trac.webkit.org/changeset/228430/webkit)), and special-case **Safari Reader configuration** (e.g. fonts) inside WebKit ([changeset 272999](https://trac.webkit.org/changeset/272999/webkit)). That is evidence Reader is **wired through WebKit/Safari**, not that the article-finding JavaScript is a supported public API.

**Uncertain:** Whether any current Reader JS still lives in the public WebKit tree. This research did not find a documented, supported `ReaderArticleFinder` (or similar) on `WKWebView`. Treat the algorithm as **Safari-private**.

### `WKWebView` has no Reader

`WKWebView` is “a platform-native view” that loads a `URLRequest` (or HTML string), **automatically loads embedded resources**, **renders**, and can **`evaluateJavaScript`**. The topic list includes loading, navigation, JS, snapshots, PDF — **not** Reader. ([WKWebView](https://developer.apple.com/documentation/webkit/wkwebview))

WWDC 2020: if you want an in-app browser **with Reader, content blockers, AutoFill**, use **`SFSafariViewController`** (“browser in a box”). Use `WKWebView` when you need to **customize** the experience. ([WWDC 2020 session 10188](https://developer.apple.com/videos/play/wwdc2020/10188/))

### `SFSafariViewController` can enter Reader — it is a UI, not a text API

Apple: the controller presents a **self-contained** web interface. It **supports Safari features such as Reader**. UI includes a **Reader button**. **“Interactions with the web interface aren’t visible to your app, and you can’t access AutoFill data, browsing history, or website data.”** If you need to **interact with content**, use `WKWebView` instead. Always present it visibly (App Store guideline). ([SFSafariViewController](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller))

You can ask it to **enter Reader if available** (`init(url:entersReaderIfAvailable:)` / `Configuration.entersReaderIfAvailable`). That still only **shows** Reader to the person. It does not return HTML. ([SFSafariViewController topics](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller))

Apple DTS (Quinn “The Eskimo!”, Nov 2017), on a thread titled “How use reader view in WebKit”: the iOS 11 replacement for the deprecated initializer is `initWithURL:configuration:` with **`entersReaderIfAvailable`** — i.e. **Safari View Controller**, answering someone who wanted Reader **inside WKWebView**. ([Forums thread 92673](https://developer.apple.com/forums/thread/92673))

WWDC 2015: `SFSafariViewController` runs in a **separate process**; the user can tap **Safari Reader** for a cleaned-up article. Same product story: UI, not an extract API. ([WWDC 2015 session 504](https://developer.apple.com/videos/play/wwdc2015/504/))

**For a headless daily digest on a Mac:** presenting `SFSafariViewController` does not give Python a string. `WKWebView` can give you a string **if you run your own extract** after load (`evaluateJavaScript` / archive of the DOM). That extract would be **yours** (Readability cousin, trafilatura, etc.), not Apple Reader.

---

## 7. Honest cannots

- **No public Apple API** for “run Safari Reader and return the article.”
- **`WKWebView` has no Reader mode** in the public docs.
- **`SFSafariViewController` Reader is a person-facing view**; the host app is barred from reading the page.
- **Readability ≠ Safari Reader.** Same family tree; Safari added render-time checks (2018 research). Behavior will diverge, especially on hidden nodes.
- **A Reader-like extract cannot create text the server never sent** and scripts never inserted.
- **Using the owner’s logged-in Safari cookies or a headless browser logged into a news site** is a **session** question (terms, risk, fragility), not an extract-algorithm question. This note does not recommend impersonating Safari to obtain paywalled HTML.
- **Open WebKit text-extraction SPI** is not documented as a substitute for Reader and is not a Python API BiteSIze can call today.

---

## 8. Recommended next experiments (this personal digest)

Goal: learn **which** of your usual sources fail because of **missing HTML** vs **static extract losing a long body that was already in the GET**. Do not treat “make it like iPhone Reader” as a single feature.

1. **Split a dozen failures by document, not by vibe.** For each URL where Kindle got a teaser and your phone’s Reader looked complete: save the BiteSIze GET HTML and note length; in Safari, use Web Inspector (or “page source”) on the **same URL in a private window** vs your normal window. If private-window source is short and logged-in source is long, Reader is not the gap — **the response** is. If private-window source already contains the article, try trafilatura / Readability on that file offline.

2. **Same bytes, two extractors.** Run current `trafilatura.extract` and Mozilla Readability (jsdom, **scripts off**, as Mozilla recommends) on the saved GET. If Readability suddenly matches Reader, the cheap win is **extractor choice on static HTML**, not a browser.

3. **Loaded DOM, still your extractor.** For sites where the GET is short but a **private** Safari tab’s **after-load** DOM is long (scripts inserted nodes), a one-off **headless WebKit/Chromium** wait-until-idle, then `outerHTML` → trafilatura/Readability, measures the **JS gap**. Judge cost (seconds per article, breakage, CPU) against the daily LaunchAgent. This is “run JS, then cousin extract,” not Apple Reader.

4. **Do not prototype `SFSafariViewController` for the digest.** It cannot export text. Fine for a human reading UI; useless for `main.py --all`.

5. **Keep archive mirrors for missing-HTML cases.** They are the existing best-effort when a public snapshot stored more HTML than today’s GET. Log which hosts are overlay-ish vs empty-body so you do not spend weeks on a browser for sites that never ship the article to anonymous clients.

6. **Decide a policy for logged-in fetches separately.** A personal tool *could* use a browser profile you already use, but that is cookie/session reuse and site terms — outside this research note. Reader itself is not a license to take text the site only gives subscribers.

If experiment 1–2 fix most of the list, stay on HTTP + a better static extractor. If experiment 3 is the only thing that matches Reader, the product choice is **optional slow path** for named sources, not replacing the whole pipeline with Safari.

---

## Constraints that bound the project

1. **Safari Reader is a post-load reading view**, offered when Safari thinks the current page is an article. ([Mac / iPhone user guides](https://support.apple.com/guide/safari/hide-ads-when-reading-sfri32632/mac))
2. **Safari’s extract uses (or used, as of 2018 research) render and visibility**, so it is not interchangeable with GET+trafilatura. ([arXiv 1811.03661](https://arxiv.org/abs/1811.03661))
3. **There is no Apple text API for Reader.** `WKWebView` has no Reader; `SFSafariViewController` Reader is UI-only. ([WKWebView](https://developer.apple.com/documentation/webkit/wkwebview), [SFSafariViewController](https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller), [DTS, thread 92673](https://developer.apple.com/forums/thread/92673))
4. **Mozilla Readability is the documented cousin** for “article from a DOM,” not a drop-in Safari clone. ([mozilla/readability](https://github.com/mozilla/readability))
5. **BiteSIze today never executes page JavaScript**; mirrors only help when a snapshot has more HTML.

---

## Source list (owners)

- Apple Support — Reader on iPhone: https://support.apple.com/guide/iphone/hide-ads-and-distractions-iphdc30e3b86/ios
- Apple Support — Reader on Mac: https://support.apple.com/guide/safari/hide-ads-when-reading-sfri32632/mac
- Apple Support — Distraction Control (not Reader): https://support.apple.com/120682
- Apple Developer — `SFSafariViewController`: https://developer.apple.com/documentation/safariservices/sfsafariviewcontroller
- Apple Developer — `WKWebView`: https://developer.apple.com/documentation/webkit/wkwebview
- WWDC 2015 — Introducing Safari View Controller (session 504): https://developer.apple.com/videos/play/wwdc2015/504/
- WWDC 2020 — Discover WKWebView enhancements (session 10188): https://developer.apple.com/videos/play/wwdc2020/10188/
- Apple DTS (Quinn) — Reader via `SFSafariViewController` configuration, not WKWebView: https://developer.apple.com/forums/thread/92673
- WebKit.org — Safari 18.0 (semantic HTML / Reader): https://webkit.org/blog/15865/webkit-features-in-safari-18-0/
- WebKit.org — Safari 18.1 (Reader history + Summarize): https://webkit.org/blog/16188/webkit-features-in-safari-18-1/
- WebKit — Reader as second page after original load (watchOS): https://trac.webkit.org/changeset/233891/webkit
- WebKit — Reader vs loader policy: https://bugs.webkit.org/show_bug.cgi?id=182697 — https://trac.webkit.org/changeset/228430/webkit
- WebKit — Reader heading heuristics: https://bugs.webkit.org/show_bug.cgi?id=225609
- WebKit — Safari Reader configuration mentioned in font sandbox: https://trac.webkit.org/changeset/272999/webkit
- WebKit — generic text extraction (not Reader API): https://github.com/WebKit/WebKit/pull/23317
- Ghasemisharif, Snyder, Aucinas, Livshits — *SpeedReader: Reader Mode Made Fast and Private*: https://arxiv.org/abs/1811.03661 — https://arxiv.org/pdf/1811.03661
- Mozilla Readability (cousin): https://github.com/mozilla/readability — Firefox Reader help: https://support.mozilla.org/kb/firefox-reader-view-clutter-free-web-pages
- WHATWG HTML — script processing model: https://html.spec.whatwg.org/multipage/scripting.html#script-processing-model
- W3C CSS 2.2 — `display`: https://www.w3.org/TR/CSS22/visuren.html#display-prop
- Trafilatura (what BiteSIze calls): https://trafilatura.readthedocs.io/en/latest/usage-python.html
- BiteSIze — `feed.py` (`_download_url`), `paywall.py` (`fetch_with_paywall_bypass`)
