# Kindle devices and EPUB interactivity — research note

**Date:** 14 August 2026  
**Scope:** Personal project (BiteSIze already builds Kindle-oriented EPUBs with ebooklib, emails them through Send to Kindle, and copies them into iCloud Books).  
**Method:** Primary sources only. Official specs, Amazon help, W3C/IDPF, KOReader docs, MobileRead / KindleModding wiki as community-primary for jailbreak *capabilities*, ebooklib GitHub. Uncertain facts are marked as such. This note does **not** describe jailbreak procedures, payloads, or exploits.

**How to read this:** Stock Kindle books do not run JavaScript. The useful “interactivity” on an unmodified e-ink Kindle is internal hyperlinks, native highlights/notes, and (separately) the Experimental Web Browser. Everything else is either a conversion loss, a website, or a jailbroken app.

---

## 1. EPUB package format

An EPUB file is a ZIP archive with a defined internal layout. W3C EPUB 3.3 (W3C Recommendation) says a publication is typically one ZIP package whose contents include a package document (metadata, manifest, spine), an EPUB navigation document, and XHTML/CSS/SVG content documents. ([EPUB 3.3](https://www.w3.org/TR/epub-33/), [EPUB 3 overview page](https://www.w3.org/publishing/epub3/))

### Official EPUB 3 spec URLs

| Document | URL | Status (as of this note) |
|---|---|---|
| EPUB 3.3 (authoring) | https://www.w3.org/TR/epub-33/ | W3C Recommendation; also https://www.w3.org/TR/epub/latest/ |
| EPUB Reading Systems 3.3 | linked from https://www.w3.org/publishing/epub3/ | Reading-system conformance |
| EPUB Accessibility 1.1 | linked from https://www.w3.org/publishing/epub3/ | Accessibility |
| EPUB 3.4 | https://www.w3.org/TR/epub-34/ | Later draft in the same family; **3.3 is the current Recommendation** cited below |

W3C’s EPUB 3.3 landing page states that EPUB 3.3 is the first W3C Recommendation of the EPUB series and is backward compatible with EPUB 3.2. ([publishing/epub3](https://www.w3.org/publishing/epub3/))

### OCF ZIP container

EPUB 3.3 section 4 defines the Open Container Format (OCF):

- The physical container is a ZIP file (`application/epub+zip`).
- The first file in the ZIP **must** be an uncompressed `mimetype` file whose contents are exactly `application/epub+zip`.
- A `META-INF/container.xml` file points at the package document (the `.opf`).
- ZIP entries may be stored uncompressed or Deflate-compressed; ZIP encryption and multi-disk spanning are forbidden. ([EPUB 3.3 §4](https://www.w3.org/TR/epub-33/#sec-ocf))

EPUB 2 used the same ZIP idea under a separate IDPF spec: Open Container Format (OCF) 2.0.1, listed as a Word document on the IDPF EPUB 2.0.1 page. ([IDPF EPUB 2.0.1](https://idpf.org/epub/201), [EPUB specs directory](https://idpf.org/epub/dir/))

### Package document (OPF), spine, navigation

The **package document** (historically `content.opf`) holds:

- **Metadata** (title, language, identifier, and so on).
- **Manifest** — every resource in the publication except `mimetype` and `META-INF` files.
- **Spine** — the default reading order: an ordered list of content documents. ([EPUB 3.3 §5](https://www.w3.org/TR/epub-33/#sec-package-doc))

EPUB 3 requires an **EPUB navigation document**: a specialized XHTML file with a machine-readable table of contents (and optional landmarks, page list). It can also be shown to the reader as a human TOC. ([EPUB 3.3 §7](https://www.w3.org/TR/epub-33/#sec-nav))

EPUB 2 used a separate **NCX** file (`application/x-dtbncx+xml`) for the table of contents. That is defined in Open Packaging Format (OPF) 2.0.1, section 2.4.1. ([OPF 2.0.1](https://idpf.org/epub/20/spec/OPF_2.0.1_draft.htm)) EPUB 3 still *allows* a legacy NCX so older reading systems can open the file; EPUB 3 reading systems are supposed to use the navigation document instead. ([EPUB 3.3 §5.9.5 NCX](https://www.w3.org/TR/epub-33/#sec-opf2-ncx))

Content is **XHTML** (and optionally SVG) plus **CSS**. EPUB 3 content documents are HTML as defined by the living HTML standard, plus CSS. ([EPUB 3.3 overview](https://www.w3.org/TR/epub-33/#sec-intro-epub-docs))

### EPUB 2 vs EPUB 3 (what actually differs for this project)

EPUB 2.0.1 is three IDPF specs: OPS (content), OPF (package + NCX), OCF (ZIP). IDPF marks EPUB 2.x obsolete and superseded by EPUB 3. ([IDPF EPUB 2.0.1](https://idpf.org/epub/201))

Practical differences that matter here:

| | EPUB 2 | EPUB 3 |
|---|---|---|
| TOC | NCX required for many reading systems | Navigation document required; NCX optional for compatibility |
| Markup | XHTML 1.1 subset (OPS) | HTML / XHTML content documents |
| Scripting | Not a first-class EPUB 2 feature | Allowed as *scripted content documents* (see below) |
| Nav in spine | Guide / NCX | `nav` document, may also appear in the spine |

**Scripting in the EPUB spec is not the same as scripting on Kindle.** EPUB 3.3 §6.3.2 says content documents **may** contain scripting (HTML `script`, and HTML **form** elements also count as scripted content). Reading systems that do not support scripting should get a fallback. ([EPUB 3.3 §6.3.2](https://www.w3.org/TR/epub-33/#sec-scripted-content)) Amazon Kindle books strip scripts (section 3). Do not assume an EPUB 3 script will run on a Kindle.

### What ebooklib (Python) can read and write

EbookLib’s own README: it is “a Python library for managing EPUB2/EPUB3. It’s capable of reading and writing EPUB files programmatically.” It supports covers, table of contents, spine, guide, and metadata. Docs: http://ebooklib.readthedocs.io. Source: https://github.com/aerkalov/ebooklib

Documented operations (README + library docs):

- `epub.read_epub(path)` — load an existing EPUB into an `EpubBook`.
- Iterate items by type (`ITEM_DOCUMENT`, `ITEM_IMAGE`, CSS as `EpubItem` with `media_type="text/css"`).
- Mutate metadata, add/replace HTML chapters (`EpubHtml`), CSS, images.
- Set `book.toc` and `book.spine`.
- Add both `EpubNcx()` (legacy NCX) and `EpubNav()` (EPUB 3 nav).
- `epub.write_epub(path, book)` — rewrite the ZIP.

BiteSIze already does this in `epub.py`: it builds an `EpubBook`, sets a spine (cover, non-linear nav, section covers, articles), adds NCX + Nav, and writes the file.

Caveat the README does not hide: rewriting an EPUB with ebooklib is a parse-and-regenerate cycle, not a byte-preserving zip edit. Complex EPUB 3 features (media overlays, some `properties`, unusual OPF) can be lost or simplified on write. Treat “edit existing `./output/*.epub`” as: read documents/CSS/OPF-equivalent objects, change XHTML/CSS, write a new EPUB, then validate with epubcheck.

---

## 2. How Amazon Kindle consumes personal documents

Kindle Store books and **personal documents** are different pipelines. BiteSIze uses the personal-document path (email Send to Kindle), not KDP publishing.

### Send to Kindle (email)

Amazon’s Send to Kindle email page:

1. Find the device’s Send to Kindle address under **Manage Your Content & Devices → Preferences → Personal Document Settings**.
2. Only addresses on the **Approved Personal Document E-mail List** may send.
3. Attach the file; a subject line is not required.
4. Supported types listed there: PDF, DOC, DOCX, TXT, RTF, HTM, HTML, PNG, GIF, JPG, JPEG, BMP, EPUB. ([Send to Kindle – Email](https://www.amazon.com/sendtokindle/email))

The same supported list appears on Amazon Customer Service: *Learn About Sending Documents to Your Kindle Library*. Upload paths: web (files 200 MB or smaller), Kindle app, desktop Send to Kindle app, or authorized email. Amazon states documents sent through Send to Kindle are protected with end-to-end encryption. ([G5WYD9SAF7PGXRNA](https://www.amazon.com/gp/help/customer/display.html?nodeId=G5WYD9SAF7PGXRNA))

Email-specific limits (*Learn How to Use Your Send to Kindle Email Address*):

- Up to 25 attachments per email.
- Up to 15 approved sender addresses.
- Total size 50 MB or less; ZIP is allowed and “the conversion service automatically opens the ZIP files and converts them to the Kindle format.”
- Delivery is attempted for up to 60 days if the device is online. ([G7NECT4B4ZWHQ8WV](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV))

Adding senders: *Add an Email Address to Receive Documents in Your Kindle Library*. ([GX9XLEVV8G4DB28H](https://www.amazon.com/gp/help/customer/display.html?nodeId=GX9XLEVV8G4DB28H))

**`@kindle.com` vs `@free.kindle.com`:** Current Send to Kindle email help (fetched August 2026) talks about “your Send to Kindle email address” and does **not** mention `@free.kindle.com`. Older Amazon-era documentation treated `@free.kindle.com` as Wi-Fi-only delivery versus 3G Whispernet charges. Whether `@free.kindle.com` still exists or still behaves that way is **not confirmed** on the current official pages cited above. Do not depend on it without checking Personal Document Settings on the live Amazon account.

### USB copy to `/documents`

Amazon’s *Connect, Browse, and Transfer Files on E-Reader* describes USB transfer. For Kindle Scribe and 2024-released devices, Amazon recommends wireless Send to Kindle (files up to 200 MB; same format list including EPUB) because macOS does not speak MTP natively. Windows typically mounts the Kindle as a drive. ([TCUBEdEkbIhK07ysFu](https://www.amazon.com/gp/help/customer/display.html?nodeId=TCUBEdEkbIhK07ysFu))

Older Amazon device help for Kindle Keyboard says to open the **Documents** (or Internal Documents) folder and drag compatible files there. ([Kindle Keyboard transfer help](https://d1ergij2b6wmg5.cloudfront.net/Ereader/Early+Generation+Device+Help/Kindle+Keyboard+3rd+Gen+Help/enUS/Kindle_Keyboard_3rd_Generation_Transfer_From_PC.html))

**Uncertain / not stated by Amazon:** current help does **not** say that a raw `.epub` copied over USB will open in the stock Kindle reader. Send to Kindle is the documented EPUB ingestion path; Amazon converts that EPUB. KDP also says sideloading is a poor test of Enhanced Typesetting (section 9). If USB is used, convert first (Calibre AZW3, or Amazon’s own conversion via email/web) unless a later Amazon page states native EPUB USB support for that firmware.

### Amazon conversion: EPUB is converted

Send to Kindle **accepts** EPUB. The email help’s ZIP sentence is explicit that Amazon **converts** attachments “to the Kindle format.” ([G7NECT4B4ZWHQ8WV](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV)) Amazon Australia’s older sibling page also noted MOBI send-to-Kindle support was reduced from November 2023. ([amazon.com.au G5WYD9SAF7PGXRNA equivalent / node 200767340](https://www.amazon.com.au/gp/help/customer/display.html?nodeId=200767340))

Amazon does **not** publish, on the personal-document help pages found for this note, a feature-by-feature list of “what survives EPUB → Kindle conversion” (AZW3 vs KFX, which CSS, whether every internal link is preserved). What *can* be said from owned sources:

- After Send to Kindle, EPUB personal documents support **highlights and text notes** on Kindle e-readers (and several apps). Kindle for Web: personal documents “aren’t supported yet.” ([Personal document file types that support notes](https://www.amazon.com/gp/help/customer/display.html?nodeId=TNtSm13k3txFI4EvDV))
- Publisher/KDP conversion (a related but not identical pipeline) **strips scripts** and only partially supports forms/frames/JavaScript (section 3). Treating personal-document conversion as *at least as hostile* to scripts and forms is the conservative reading; Amazon does not document extra JS for personal docs.
- Kindle Previewer is Amazon’s tool for seeing how an EPUB will look after Kindle conversion, including Enhanced Typesetting. ([Kindle Previewer](https://kdp.amazon.com/en_US/help/topic/G202131170))

Related: *Tips about converting personal documents to a Kindle format* exists as a help node (`TWXpUGw76dtEg2VD9P`) and is linked from the email page. The public fetch of that page was mostly Scribe layout options (“like a printed document” vs adjustable layout), not an EPUB CSS survival matrix. ([TWXpUGw76dtEg2VD9P](https://www.amazon.com/gp/help/customer/display.html?nodeId=TWXpUGw76dtEg2VD9P))

### Kindle Previewer 3

Amazon: Kindle Previewer is a free desktop app to preview how an eBook will look on Kindle devices/apps, including Enhanced Typesetting. It opens `.epub`, `.htm`, `.html`, `.xhtml`, `.opf`, `.kpf`, `.doc`, `.docx`. It can preview by device type (tablet, phone, e-reader), orientation, and font. User guide (v3.104.0, April 2026): https://kindlepreviewer3.s3.amazonaws.com/UserGuide320_EN.pdf. KDP help: https://kdp.amazon.com/en_US/help/topic/G202131170. Product/download: https://www.amazon.com/Kindle-Previewer/b?node=21381691011

Amazon no longer recommends sideloading to a device as the way to test Enhanced Typesetting. ([Paths to Getting Your Content on Kindle](https://kdp.amazon.com/en_US/help/topic/G79CTKR8BX79E96L))

---

## 3. Kindle HTML/CSS/JS support in **books** (not the browser)

This section is about the **book renderer**, not Experimental Browser.

Current Amazon publishing rules live in two places that agree:

- HTML user guide hub: [Kindle Publishing Guidelines](https://kdp.amazon.com/help/topic/GU72M65VRFPH43L6) (page dated June 2026 in the KDP chrome).
- PDF: [Amazon Kindle Publishing Guidelines version 2026.2](http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf) (`kindlegen.s3.amazonaws.com`).

### No JavaScript in Kindle books

PDF §6.1: Kindle supports most HTML 5.0 features, but **forms, frames, and JavaScript are not fully supported**.

PDF §6.3, title “Avoid Using Scripting”: **“Scripting is not supported. All scripts are stripped from the source during conversion.”** Same statement on the German KDP HTML page (official Amazon locale of the same topic). ([PDF 2026.2](http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf), [HTML- und CSS-Richtlinien](https://kdp.amazon.com/de_DE/help/topic/GP2Z9DD4F2N4QKCY))

**Stock Kindle books do not run JavaScript.** Do not design quizzes, scoring, `localStorage`, or form posts inside the EPUB for the Kindle book renderer. EPUB 3’s scripted-content feature is irrelevant on stock Kindle after conversion.

Forms: Amazon’s wording is “not fully supported,” plus scripts (which HTML forms usually need) are stripped. There is **no** Amazon statement that interactive HTML forms or quizzes execute in the book renderer. Treat forms as non-working for this project.

### Supported HTML/CSS (KF8 / Enhanced Typesetting)

Tag and property tables:

- [HTML and CSS Tags Supported in Kindle Format 8](https://kdp.amazon.com/en_US/help/topic/GG5R7N649LECKP7U)
- [Attributes and Tags Supported by Enhanced Typesetting](https://kdp.amazon.com/en_US/help/topic/GB5GDY7WAJDN9GFK)

Useful CSS facts from the KF8 table (not exhaustive): `@font-face` yes; `position` yes; `float` yes; many structural/pseudo-class selectors (`:nth-child`, `::before`, `::after`) **no**; `max-width` / `max-height` **no**. Body text in reflowable books should stay at defaults so the reader’s font slider works. ([Text Guidelines – Reflowable](https://kdp.amazon.com/en_US/help/topic/GH4DRT75GWWAGBTU)) BiteSIze’s existing CSS already sizes type in `em` for that reason.

### Internal hyperlinks — the main stock-Kindle “interactivity”

[Hyperlink Guidelines](https://kdp.amazon.com/en_US/help/topic/GQ6JQ7FM6C72HE4X):

- Internal links may point at chapters, sections, appendix, glossary, “see page 73,” footnotes.
- Footnotes should be **bidirectional** (text ↔ note). On some devices the note opens as a pop-up.
- **Non-footnote** internal links should **not** be bidirectional (A→B and B→A), because that can trigger the footnote pop-up. Pattern: A→B and B→C (e.g. TOC entry → section, section heading → chapter heading).
- Internal hyperlinks are **not currently supported on e-reader devices in fixed-layout books**.

That is the supported mechanism for choose-your-own-adventure and link-based quizzes on stock Kindle: ordinary `<a href="choice-b.xhtml">` (or `#id`) links to other spine documents or fragments.

External links: allowed only if they “directly enhance” the book; Amazon may remove them; **links to web forms that request customer information are prohibited** in KDP books; external links also do not work on e-reader **fixed-layout**. For a personal document this KDP commercial-policy list is not a Kindle firmware spec, but the e-reader limitation on fixed-layout links is a device fact.

### Images, fonts

[Image Guidelines – Reflowable](https://kdp.amazon.com/en_US/help/topic/G75V4YX5X8GRGXWV) and PDF §11.4:

- JPEG and PNG; no TIFF, no multi-frame GIF, no transparency (transparent areas become white).
- sRGB / RGB; CMYK is converted or unsupported depending on the page (HTML guidelines: use sRGB, Kindle converts CMYK; cover checklist: use RGB, not CMYK).
- Pictorial images: aim for ≥60% of screen width; images with text: ≥80%.
- Interior full-page quality bar in the PDF: 300 ppi on a 4″×6″ canonical page → **1200×1800 pixels** minimum for a full-page image. Cover images: at least 1200 px on the long side in the reflowable HTML page; marketing cover in the PDF is 2560×1600 recommended.
- Alt text required for meaningful images.
- SVG: KF8 table says only SVG is supported among “object-like” cases in one row, but the reflowable image guidelines warn that SVG tags can cause errors and recommend `<img>` instead. Prefer raster for BiteSIze unless Previewer proves SVG on the target firmware.

Fonts: `@font-face` is in the KF8 CSS table. Reflowable text guidelines cover embedded fonts and warn against forcing body typeface/size (overrides the user’s settings). OpenType/TrueType are the usual Kindle-embedded formats in the PDF’s font section; Type 1 PostScript is not recommended.

### Audio, video, quizzes on e-ink

[Creating Kindle Editions with Audio/Video Content](https://kdp.amazon.com/en_US/help/topic/GCRRGQL2SPQXYXD4): audio/video Kindle editions are for Fire tablets (2nd gen+) and iOS (iPad/iPhone/iPod touch), **reflowable only**. **“Audio and video content is not supported on Kindle E-reader devices (customers can read the book, but any audio or video is replaced with a message that it is not supported on this device).”** Fixed-layout + audio/video is also unsupported.

Quizzes that need script, timers, or persisted scores: not in the book renderer (scripts stripped). Link-based Q&A pages are the stock path (section 6).

### Fixed-layout vs reflowable

[Paths to Getting Your Content on Kindle](https://kdp.amazon.com/en_US/help/topic/G79CTKR8BX79E96L) and Previewer FAQ:

- **Reflowable:** text reflows with font size and screen; Enhanced Typesetting applies to reflowable EPUB/DOC(X)/HTML. This is the right format for BiteSIze magazines and gamebooks.
- **Fixed-layout / print replica:** pixel-placed pages; no user font resize in the same way; **internal and external hyperlinks are not supported on e-readers** for fixed-layout (Hyperlink Guidelines). Comics/children’s books are a separate Guided View path.

Do not use fixed-layout for interactive link books on e-ink.

---

## 4. Native highlighting and notes

### My Clippings.txt

Amazon does not publish a format spec for `My Clippings.txt`. Community-primary sources (MobileRead) agree:

- On a physical Kindle e-reader (not Fire, not the phone app), highlights, notes, and bookmarks are appended to a plaintext log.
- Location: the device’s **documents** folder, filename `My Clippings.txt`, visible when the Kindle is mounted over USB. ([MobileRead: How can I save my highlights](https://www.mobileread.com/forums/showthread.php?t=235233), [MobileRead: How do I move notes](https://www.mobileread.com/forums/showthread.php?t=113205))

Typical record shape (community-observed, not an Amazon spec): title line, a metadata line (`Your Highlight` / `Your Note` / `Your Bookmark`, location or page, timestamp), blank line, quoted text or note body, then a `==========` separator. Firmware differences exist; treat parsing as best-effort.

MobileRead also notes sidecar folders such as `My Clippings.sdr`; the `.txt` file is the log most tools parse. ([MobileRead thread on .sdr](https://www.mobileread.com/forums/showthread.php?t=347190))

### Amazon cloud / Kindle notebook

- In-book notebook UI: Amazon help *View Your Notebook in Kindle for Web* — notes, highlights, bookmarks in one list. ([TS3oZMNGd9T0s62hVd](https://www.amazon.com/gp/help/customer/display.html?nodeId=TS3oZMNGd9T0s62hVd))
- Standalone web notebook used in the wild: `https://read.amazon.com/notebook`. Amazon does not spell out on the personal-document notes page that **personal documents** appear there. The personal-document notes table says Kindle for Web does **not** support personal documents yet. ([TNtSm13k3txFI4EvDV](https://www.amazon.com/gp/help/customer/display.html?nodeId=TNtSm13k3txFI4EvDV))

Practical split for BiteSIze: **device `My Clippings.txt` is the reliable export for personal documents**; cloud notebook is aimed at Store books (ASIN/EBOK). Do not plan a cloud-API integration Amazon has not documented for PDOC.

### ASIN vs personal documents

Amazon Store books are identified as Kindle Store items (commonly a 10-character ASIN, CDE type **EBOK** in community terminology). Personal documents sent through Send to Kindle are **PDOC**; Amazon assigns its own identifiers at conversion time. MobileRead (jhowell): Amazon identifies books by CDE type + ASIN; values in a file you email are **replaced by Amazon**; highlight positions are **offset numbers specific to that converted file**. ([MobileRead: Associate personal documents](https://www.mobileread.com/forums/showthread.php?t=293345))

That is community-primary, not an Amazon help page, but it is the standard explanation from people who reverse-engineer Kindle formats. Amazon’s own help never says “personal documents get a 32-character ASIN.”

### Do highlights survive re-sending a replaced EPUB with the same title?

**Amazon does not document this.** Closest official signal: even for **Store** books, customers report losing highlights when Amazon pushes a new version; staff/community replies say it depends how much the file changed because highlights are tied to locations. ([Amazon forum: notes lost on book update](https://www.amazonforum.com/s/question/0D54P00006zSvHcSAK/no-backup-of-highlights-or-notes-and-other-annotations-when-you-update-to-a-new-version-of-a-kindle-book))

For personal documents, the conservative and likely-correct model is:

- A new Send to Kindle of the “same” title is a **new PDOC** (new Amazon identifier, new location map).
- In-book highlight markers on the new file should **not** be assumed to reattach.
- `My Clippings.txt` **keeps historical rows** keyed by the title string as the Kindle recorded it at highlight time — useful as an archive, not as live overlays on the new file.

Same title in OPF metadata is not an Amazon identity. If BiteSIze needs durable notes, parse Clippings (or ask the reader to export) rather than relying on WhisperSync for PDOC.

---

## 5. Kindle Experimental Web Browser

This is a **separate app** from the book renderer. JavaScript that is stripped from books can exist here.

### What Amazon’s device user guides say

Amazon Kindle user guides (Voyage and Keyboard-era wording, widely reprinted from Amazon’s manuals):

- The Kindle includes an **experimental** web browser.
- It **supports JavaScript, SSL, and cookies**.
- It **does not support media plug-ins** (Flash, Shockwave, etc.) or Java applets.
- **Wi-Fi** is required for most sites.
- Open it from the menu: **Experimental Browser** (wording varies by generation: Menu → Experimental Browser, or an Experimental item then Launch browser).
- Settings include Clear History, Clear Cookies, **Disable JavaScript**, Disable Images.
- Address field: type a URL; for `https://`, older keyboard guides said to delete the prefilled `http://`. Article Mode, Bookmarks, History are in the browser menu.

Sources for that language: Amazon Voyage User’s Guide (reprinted, e.g. [manymanuals Voyage p.34](https://amazon.manymanuals.com/e-book-readers/voyage/users-guide-46412/34)), Kindle Keyboard user-guide chapter *Accessing the Web* (reprinted [manualsdump KNDKYBRD3G](https://manualsdump.com/en/manuals/amazon-kndkybrd3g/149087/73)). These are Amazon’s own user-guide sentences, not third-party analysis.

Amazon’s consumer help index used for this note does **not** currently have a rich, modern “Experimental Browser” article comparable to Send to Kindle. Treat the device user guide as the official feature list.

### Known limitations (community-primary; Amazon does not publish a WebKit version)

- The browser is old WebKit wrapped in Amazon UI. MobileRead: “built on webkit but is otherwise part of Amazon’s proprietary code.” ([HTML5/CSS3 Support for Kindle’s Experimental Browser](https://www.mobileread.com/forums/showthread.php?t=316334))
- No tabs in the user-guide feature list (bookmarks/history only).
- E-ink: slow refresh, poor animation, high click latency reported on older firmware. ([Kindle touch browser javascript capabilities](https://www.mobileread.com/forums/showthread.php?t=166843))
- Modern CSS (flexbox, grid, `fetch`, ES6) is incomplete; `-webkit-` prefixes sometimes help. Independent PW3 notes: subset of ES5, `fetch` missing, `localStorage` present on that device — **device-specific, not Amazon-documented**. ([Thor Galle, PW3 browser notes](https://thorgalle.me/notes/documentation-for-the-kindle-browser))
- HTTPS: Amazon user guides claim SSL. Community reports of outdated root certificates and Let’s Encrypt failures on some firmware. ([Amazon customer forum: outdated root certificates](https://www.amazonforum.com/s/question/0D56Q00008pHLpmSAG/outdated-or-missing-root-certificates-in-latest-firmware)) Prefer simple HTTP on the LAN for a companion site, or test HTTPS on the actual device.
- Forms: cookies + JavaScript are officially supported, so **HTML forms in the browser** are in-scope in a way they are **not** in books. How well a given form works is firmware-specific.

### Can a local website (LAN IP) be reached?

**Amazon does not say.** Official constraint is: Wi-Fi, HTTP/HTTPS.

Community: people do open `http://192.168.x.x:port/` from the Experimental Browser when the Kindle and the server share Wi-Fi (example workflow in [kindle-web-tools](https://github.com/martin-at-ipal/kindle-web-tools), which states it needs no jailbreak). Accessing **localhost / the Kindle’s own IP** from the same device is a different, often blocked, case (MobileRead browser-patch thread).

**Working assumption for BiteSIze, to be verified on hardware:** a computer on the same Wi-Fi, serving a simple HTML quiz over HTTP, is reachable if the Kindle browser can load other websites. It is not guaranteed; captive-portal and TLS issues are common. This is the honest companion-site path for scored tests without jailbreak.

---

## 6. Gamebooks / CYOA / “Murdoku”-style books on Kindle

### What Murdoku actually is

**Murdoku is not software inside a Kindle book.** Publisher copy (Penguin / Puzzlewright): 80 murder-mystery **logic puzzles** on double-page spreads; sudoku-like placement of suspects on a visual crime-scene grid; print puzzle book. ([Penguin: Murdoku](https://www.penguin.co.uk/books/476207/murdoku-by-garand-m/9781405985451), [Hachette / Puzzlewright](https://www.hachettebookgroup.com/titles/manuel-garand/murdoku/9781454961796/?lens=puzzlewright-press))

Look-inside reviews describe left-page clues + right-page grid, pencil work, page turns — not a runtime. ([YouTube review: How Murdoku Works](https://www.youtube.com/watch?v=ACzBkECJVd0)) There is a **separate** browser game at murdoku.fans with click-to-place and Submit; that is a website, not the Kindle book renderer. ([murdoku.fans how to play](https://murdoku.fans/en/how-to-play/))

For BiteSIze, “Murdoku-style” on **stock Kindle** means: puzzle pages the reader solves with brain + optional highlights, or link-choice pages — not an in-book engine.

### EPUB techniques that work without JavaScript

These are ordinary EPUB/Kindle hyperlinks (section 3):

1. **Choice links** — “Turn to A” → `a.xhtml`; “Turn to B” → `b.xhtml`. Spine can include all branches (linear or `linear="no"` for extra pages). EPUB 3 spine allows non-linear items; BiteSIze already marks nav `("nav", "no")`.
2. **Quiz pages** — stem + three links (A/B/C) to **result pages** (correct / try again / explanation). Return link on the result page should follow Amazon’s non-footnote rule (do not make a bidirectional pair that looks like a footnote).
3. **Hidden answers** — put the answer on a later spine item or after a “Show answer” link. CSS `display:none` is a bad hide: Kindle Previewer error E24010 warns TOC/hyperlinks to `display:none` / `visibility:hidden` ids fail. ([Enhanced Typesetting attributes page](https://kdp.amazon.com/en_US/help/topic/GB5GDY7WAJDN9GFK)) Prefer a separate page, not a CSS hide.
4. **CYOA loops** — links among XHTML files. The reader’s “state” is only **which page they are on**. Back button / history is the device’s, not yours.

**Why this works without JS:** the Kindle book engine implements HTML `<a href>` internal navigation. That is specified and QA’d by Amazon (Hyperlink Guidelines). No script, no form, no server.

### What does **not** work on stock Kindle books

| Wanted behavior | Stock book renderer |
|---|---|
| Persist answers across sessions | No (no script, no form storage) |
| Score / grade a test | No (unless you fake it with one results page per full path — combinatorial explosion) |
| Random questions | No |
| Timed tests | No |
| Audio/video prompts on e-ink | Replaced with “not supported” ([KDP audio/video](https://kdp.amazon.com/en_US/help/topic/GCRRGQL2SPQXYXD4)) |
| HTML forms | Not fully supported; scripts stripped ([Guidelines §6.1–6.3](http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf)) |

Those features need a **website in Experimental Browser**, or **jailbreak apps** (KOReader plugins, RAnki, etc. — capability only, section 7).

---

## 7. Jailbreak / expanded Kindle — capability level only

**This section does not describe how to jailbreak.** No payloads, no file-replacement steps, no CVE reproduction, no AdBreak procedure.

### Video named in the brief

https://www.youtube.com/watch?v=l4ZliC82RtA — community video whose transcript covers an **AdBreak-era** Kindle jailbreak, then **KOReader**, **KUAL**, a package/app-store style launcher, and emulators including **Gambit** (Game Boy). It also states firmware is patched quickly and that written KindleModding guides outlive any video. Use it only as a pointer to the *kind of* capabilities people discuss. **Do not follow video steps from this repo.**

### What KindleModding says a jailbreak *is*

KindleModding overview: jailbreaking lets you **run external code** (for example KOReader or other apps). It is a process, not a replacement OS. Store, Kindle Unlimited, and stock features remain. Methods change as Amazon patches them; the site’s wizard is meant to pick a current method. Firmware can ship un-jailbreakable. ([KindleModding: Jailbreaking Your Kindle](https://kindlemodding.org/jailbreaking/))

Example **capabilities** listed on that overview (not instructions): KOReader; flashcard apps (RAnki); extra Bluetooth uses; games; custom screensavers; patched browser / VNC / SSH.

KUAL (Kindle Unified Application Launcher) is the usual menu for homebrew once a device is already jailbroken. ([KindleModding KUAL page exists](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/) — linked only as evidence that KUAL is a launcher, not as a how-to.)

**Firmware is a moving target.** Amazon patches. This note will go stale. Anyone considering that path must read KindleModding themselves and accept the risk. This project should not require jailbreak for Phase 1–3.

### What KOReader official docs say it enables

KOReader is an open-source document viewer for e-ink (Kindle among other brands). Official docs:

- User guide: https://koreader.rocks/user_guide/
- README/features: https://koreader.rocks/doc/topics/README.md.html
- SSH wiki: https://github.com/koreader/koreader/wiki/SSH

Documented capabilities relevant here:

- **Native EPUB** (and PDF, DjVu, MOBI, HTML, TXT, …) — not Amazon’s converted personal-document pipeline. ([README features](https://koreader.rocks/doc/topics/README.md.html))
- Reflowable typesetting the user controls (fonts, CSS tweaks, margins, hyphenation).
- **File manager**; USB/cloud/Calibre wireless; **SSH/SFTP server** on Kindle (with a password warning). ([User guide](https://koreader.rocks/user_guide/))
- **Plugins** (Calibre, news downloader, Wallabag, statistics, exporters). Highlights can be exported as text, Markdown, HTML, JSON, or Kindle clippings format.
- Installation on Kindle, in KindleModding’s own words, assumes a jailbroken device. ([KindleModding KOReader page](https://kindlemodding.org/jailbreaking/post-jailbreak/koreader.html))

KOReader is a **better EPUB 3 reader** than stock Kindle for CSS and unconverted EPUB. It still is not a browser: in-book JavaScript is not the reason to use it. Use it for faithful EPUB, dictionaries, and file management.

### Stock path vs jailbroken path for BiteSIze

| | Stock Kindle | Jailbroken + KOReader (and friends) |
|---|---|---|
| Delivery | Send to Kindle (Amazon converts EPUB) | Drop EPUB on device; KOReader opens it |
| Interactivity in the file | Internal links only | Still mostly links, but CSS/EPUB3 closer to source; plugins possible |
| Tests with scoring | Companion website in Experimental Browser | Browser patches / other apps / not assumed |
| Notes | Highlights + `My Clippings.txt` | KOReader highlights + export plugins |
| Risk | Amazon account / conversion quirks | Warranty, patches, breakage; out of scope to implement |

**Recommendation:** design all BiteSIze book formats for **stock**. Treat jailbreak as an optional reader the owner may install; do not build features that only work there.

---

## 8. Practical architecture for this project (BiteSIze)

Existing pieces: `epub.py` (ebooklib, Kindle-oriented CSS, magazine spine), `kindle.py` (SMTP to `@kindle.com` from an approved sender), iCloud Books copy (`books.py` / `icloud_books_dir`). Output lives under `./output/*.epub` (gitignored). Inspected 14 August 2026: `Resumo de Notícias - 14 agosto 2026 0731.epub` has **153 XHTML documents**, one `style.css`, cover + section covers + paged indexes + articles. That is the file an editor must round-trip.

The local dashboard (`dashboard.py`) binds **127.0.0.1:8765** on purpose. A Kindle on Wi-Fi cannot open it unless the bind address is changed to the LAN. A Cursor `.canvas.tsx` can map a book in the IDE; it cannot `fetch()` or write the EPUB zip. Real edits are Python + ebooklib on disk.

### Phase 1 — EPUB editor for existing `./output/*.epub`

Parse with `epub.read_epub`, edit `EpubHtml` / CSS / metadata / spine, `write_epub`, then **epubcheck** and **Kindle Previewer**. Do not expect round-trip perfection for exotic OPF. Keep NCX + Nav as BiteSIze already does. Stay reflowable; keep body font sizes in `em`.

### Phase 2 — magazine EPUBs

Already partly exists (section covers, non-linear nav, magazine cover JPEG). Align images with Amazon’s JPEG/PNG + alt-text rules. Preview in Kindle Previewer rather than trusting USB sideload. Send to Kindle remains the delivery path.

### Phase 3 — interactive gamebooks via internal links

Implement CYOA / quizzes as extra XHTML spine items and `<a href>` choices. Follow Hyperlink Guidelines (no fake footnotes). Test every link in Previewer’s link filter. This is the honest “interactive Kindle book” for stock devices.

### Phase 4 — study tests

Three layers, increasing power and friction:

1. **Stock book:** link-based quizzes (A/B/C → result pages). No score persistence.
2. **Companion site in Experimental Browser:** real forms, scoring, timing — simple HTML/JS, preferably HTTP on LAN; verify on the physical Kindle. Put the URL in the EPUB as an external link (may or may not be pleasant on e-ink; browser is a separate app).
3. **KOReader / jailbreak apps:** only if the device is already expanded; flashcards (RAnki) are a KindleModding-listed study capability, not something BiteSIze should ship.

### Phase 5 — notes via native highlights + `My Clippings.txt`

Teach/use Kindle highlights. Periodically copy `documents/My Clippings.txt` over USB and parse by title. Do not promise that re-emailing a digest with the same title keeps in-book highlight marks. Cloud notebook is optional and likely Store-book-only.

### Honest stock-Kindle cannots (checklist)

- No JavaScript in the book.
- No reliable HTML forms, scoring, random, or timers in the book.
- No e-ink audio/video in the book.
- No assumption that USB raw EPUB works.
- No assumption that highlights reattach after a new Send to Kindle.
- Experimental Browser is a 2010s web client, not Chrome.

---

## 9. Libraries and tools (official docs)

| Tool | Role | Official docs |
|---|---|---|
| **ebooklib** | Read/write EPUB 2/3 in Python | https://github.com/aerkalov/ebooklib — README; http://ebooklib.readthedocs.io |
| **Amazon Kindle Previewer** | See Kindle conversion + Enhanced Typesetting | https://kdp.amazon.com/en_US/help/topic/G202131170 — User Guide PDF https://kindlepreviewer3.s3.amazonaws.com/UserGuide320_EN.pdf |
| **Kindle Publishing Guidelines** | HTML/CSS/links/images/no scripting | HTML hub https://kdp.amazon.com/help/topic/GU72M65VRFPH43L6 — PDF 2026.2 http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf |
| **epubcheck** | Conformance checker for EPUB 2 and 3 (W3C / DAISY) | https://www.w3.org/publishing/epubcheck/ — https://github.com/w3c/epubcheck |
| **Calibre** (optional) | Library, conversion, editor; USB send | https://calibre-ebook.com/help — conversion manual https://manual.calibre-ebook.com/conversion.html |
| **KOReader** | Jailbroken-device reader, EPUB, SSH, plugins | https://koreader.rocks/user_guide/ |
| **Send to Kindle** | Personal document delivery | https://www.amazon.com/sendtokindle/email — https://www.amazon.com/gp/help/customer/display.html?nodeId=G5WYD9SAF7PGXRNA |

Calibre is optional for BiteSIze: Amazon already converts EPUB on Send to Kindle. Calibre is useful to inspect OPF, convert for USB experiments, or repair metadata. It is not the Kindle renderer.

---

## Constraints that bound the project

1. **Stock Kindle books do not run JavaScript**; Amazon strips scripts on conversion. ([Guidelines §6.3](http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf))
2. **Send to Kindle converts EPUB** into a Kindle personal document; delivery needs an approved sender and the device’s `@kindle.com` (or current Send to Kindle) address. ([sendtokindle/email](https://www.amazon.com/sendtokindle/email), [G7NECT4B4ZWHQ8WV](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV))
3. **Internal hyperlinks are the supported interactivity** on e-ink books; keep books reflowable. ([Hyperlink Guidelines](https://kdp.amazon.com/en_US/help/topic/GQ6JQ7FM6C72HE4X))
4. **Scoring, persistence, random, and timers** need a website (Experimental Browser) or non-stock apps — not the book file.
5. **Highlights on personal documents** live reliably in `My Clippings.txt` on the device; re-sending a “same title” EPUB should be treated as a new document. (Amazon notes table + MobileRead PDOC identity; Amazon silent on re-send.)

---

## Source list (owners)

- W3C EPUB 3.3: https://www.w3.org/TR/epub-33/ — https://www.w3.org/publishing/epub3/
- IDPF EPUB 2.0.1 OPF/OPS: https://idpf.org/epub/20/spec/OPF_2.0.1_draft.htm — https://idpf.org/epub/20/spec/OPS_2.0_latest.htm — https://idpf.org/epub/201
- ebooklib: https://github.com/aerkalov/ebooklib
- Amazon Send to Kindle: https://www.amazon.com/sendtokindle/email — help nodes G5WYD9SAF7PGXRNA, G7NECT4B4ZWHQ8WV, GX9XLEVV8G4DB28H, TNtSm13k3txFI4EvDV, TCUBEdEkbIhK07ysFu
- Amazon KDP / Previewer / Guidelines: GU72M65VRFPH43L6, G202131170, GQ6JQ7FM6C72HE4X, GG5R7N649LECKP7U, G75V4YX5X8GRGXWV, GCRRGQL2SPQXYXD4, G79CTKR8BX79E96L, GH4DRT75GWWAGBTU — PDF http://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf
- epubcheck: https://www.w3.org/publishing/epubcheck/
- Calibre: https://manual.calibre-ebook.com/conversion.html
- KOReader: https://koreader.rocks/user_guide/ — https://koreader.rocks/doc/topics/README.md.html
- KindleModding (capabilities only): https://kindlemodding.org/jailbreaking/
- Murdoku (print): Penguin and Puzzlewright URLs in §6
- Experimental Browser: Amazon device user guides (Voyage / Keyboard reprints cited in §5)
- My Clippings location: MobileRead threads cited in §4
