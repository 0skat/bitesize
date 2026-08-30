# Kindle personal-document cleanup — research note

**Date:** 30 August 2026  
**Scope:** Personal project (BiteSIze emails a daily magazine EPUB to an approved `@kindle.com` address via SMTP; old editions accumulate in the Amazon library and on the device). Stock Kindle e-reader, not jailbroken. Personal documents via Send to Kindle, not KDP store books.  
**Method:** Primary sources only. Amazon Customer Service help pages, Send to Kindle product pages, Kindle Store Terms of Use, Amazon Conditions of Use, Amazon Selling Partner API documentation, Calibre manual. Community forum posts are cited only where Amazon has no published answer and are marked as such. This note does **not** describe jailbreaks, cookie theft, credential scraping, or reverse-engineered Amazon APIs as implementation paths.

**How to read this:** Amazon gives you good tools to **send** personal documents and mediocre tools to **remove** them at scale. There is no official “delete after N days” switch. Cleanup is manual through Amazon’s website or (on newer e-readers) one title at a time on the device. BiteSIze can control what it **sends** and what it keeps **locally**; it cannot safely automate deletion from the user’s Amazon account.

---

## Decision-relevant finding

**Amazon does not offer an official auto-expire or auto-delete policy for Send-to-Kindle personal documents.** The only “automatic” personal-document setting Amazon documents is **Personal Document Archiving**, which controls whether incoming documents are **stored in your cloud library** — it is not a retention/TTL feature and disabling it stops future cloud storage; it does not age out old items. ([Disable Document Archiving](https://www.amazon.com/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW))

Deletion is **manual**: Manage Your Content and Devices (web), or **Remove download** / **Permanently delete** on the Kindle e-reader. ([Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD)) There is **no public, documented Amazon API** for a consumer to delete personal documents programmatically. The Selling Partner API is for marketplace sellers, not personal libraries. ([SP-API overview](https://developer.amazonservices.com/)) Automating the private AJAX behind the website would run against Amazon’s Conditions of Use prohibition on “data mining, robots, or similar data gathering and extraction tools.” ([Conditions of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=508088))

For BiteSIze specifically: daily filenames already include a date/time stamp (`Resumo de Notícias - 30 agosto 2026 0650.epub`), so resending does **not** replace prior editions — each morning adds another cloud item. The practical fix is a **human housekeeping habit** (or accepting clutter), not a BiteSIze feature that logs into Amazon.

---

## 1. Does Amazon auto-expire or auto-delete Send-to-Kindle personal documents after N days?

**No — not in any Amazon help page reviewed.**

What Amazon *does* document:

| Setting / behavior | What it actually does | Source |
|---|---|---|
| **Personal Document Archiving** (“Enable personal document archiving to my Kindle library”) | When enabled (default path for Send to Kindle), documents are **stored** in Manage Your Content and Devices. Disabling stops **future** automatic cloud storage; it is not described as deleting existing items. | [Disable Document Archiving](https://www.amazon.com/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW) |
| **Send to Kindle delivery retries** | Amazon attempts delivery for up to **60 days** if the device is offline — a delivery queue, not a deletion timer. | [Learn How to Use Your Send to Kindle Email Address](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV) |
| **Kindle Store subscription content** | Subscription/membership content (Kindle Unlimited, Prime Reading, etc.) is licensed only while subscribed — **not applicable** to personal documents you email in. | [Kindle Store Terms of Use §1](https://www.amazon.com/gp/help/customer/display.html?nodeId=201014950) |

**Not found in official Kindle e-reader help:** a documented “Quick Archive” or “remove unread docs after X days” setting for stock Paperwhite/Oasis-class devices. Amazon forum posts describe storage-management behavior on some **Fire** tablets and anecdotal auto-removal of **local downloads** on newer Paperwhites; treat those as **community reports**, not product spec. ([Amazon forum: Document Deleting Themselves](https://www.amazonforum.com/s/question/0D56Q0000Ba9xmVSQQ/document-deleting-themselves))

**Bottom line:** There is no supported “TTL = 7 days” for personal docs. Old BiteSIze digests stay until you delete them.

---

## 2. Remote deletion — website, apps, API?

### Official UI paths

**Manage Your Content and Devices (web)** is the canonical cloud library manager. Personal documents sent via Send to Kindle appear under the **Content** tab; Amazon forum guidance (repeated across many threads) says to change the content-type filter from **Books** to **Docs** — Send-to-Kindle items are classified as docs, not purchased books. Deletion there removes the item from the account cloud; sync the device afterward. ([Amazon forum: Cannot delete personal documents](https://www.amazonforum.com/s/question/0D54P00006zSzy3SAC/cannot-delete-personal-documents-from-kindledevice-and-cloud), [Cloud Drive FAQs — remove imported files at Manage Your Content and Devices](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIh9JOMGAKr7bY4zqu))

**Kindle e-reader (stock):**

- **Remove download** — removes the local file; content stays in the cloud and can be redownloaded. ([Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD))
- **Permanently delete** — removes from cloud account and all registered devices. Amazon’s help text is written for purchased books (“repurchase”); for personal docs the effect is permanent loss of that uploaded file. (Same page.)

**Deliver / Remove from Device (web):** For purchased books, Manage Your Content and Devices offers per-device delivery removal without deleting the purchase. Personal documents use the same portal; Send to Kindle docs are managed as docs. ([Send Books to Your Kindle E-Reader Manually](https://www.amazon.com/gp/help/customer/display.html?nodeId=GGLBJ4VR79NSB26W))

**Kindle apps:** Desktop/mobile apps document **Remove from Device** (local home-screen cleanup), not account-level deletion. ([Add or Remove Books from Your Kindle for Windows App](https://www.amazon.com/gp/help/customer/display.html?nodeId=GJJ4R3X5A6QD297C))

### Documented API?

| API | Consumer Kindle library delete? | Source |
|---|---|---|
| **Selling Partner API (SP-API)** | **No.** REST API for selling partners: orders, listings, inventory, etc. | [developer.amazonservices.com](https://developer.amazonservices.com/) |
| **Send to Kindle (email / web upload)** | **Send only.** No delete endpoint documented. | [Learn About Sending Documents](https://www.amazon.com/gp/help/customer/display.html?nodeId=200767340), [Send to Kindle Email](https://www.amazon.com/sendtokindle/email) |
| **Undocumented “Manage Your Content” AJAX** | Exists in the wild (community reverse-engineering); **not official**, can break without notice, and conflicts with Conditions of Use. **Out of scope for BiteSIze.** | [Conditions of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=508088) |

**Operational note (community, not spec):** Cloud deletes sometimes show “queued for deletion” and can take hours before the list refreshes clean. If deletes appear to fail, confirm the **Docs** filter and wait/sync. ([Amazon forum: Not able to delete personal documents](https://www.amazonforum.com/s/question/0D54P00007aTwD0SAK/not-able-to-delete-personal-documents-stored-in-kindle-cloud))

---

## 3. Resending the same filename / title — replace or duplicate?

**Official Amazon guidance:** Sending the **same personal document multiple times creates multiple copies** in the library; there is no documented deduplication-by-filename. ([Amazon forum: Duplicate Books Through Email Transfer](https://www.amazonforum.com/s/question/0D54P00006zIpIfSAK/duplicate-books-through-email-transfer))

**BiteSIze today:** `main.py` names each EPUB with a date/time suffix (`{digest_title} - {format_digest_timestamp(now)}.epub`), and `kindle.py` uses `epub_path.stem` as the email subject. Each daily run therefore produces a **distinct** cloud item even if the magazine structure is identical.

**Uncertain / community only:** MobileRead and Calibre users report that Amazon *sometimes* treats identical title+author metadata as one book and keeps the latest — not documented by Amazon and unreliable for a daily digest whose title changes only by date. Do not rely on “overwrite by resending.”

**Publisher updates (purchased Kindle books):** Amazon may offer corrected **store** editions; that workflow does not apply to personal EPUBs you own. ([MobileRead: Kindle Duplicates](https://www.mobileread.com/forums/showthread.php?t=144692) — community discussion of store updates, not Send to Kindle.)

---

## 4. Device-side: archive vs delete, cloud vs device, collections, storage

### Terminology (Amazon help)

| Action | Device storage | Cloud library | Primary source |
|---|---|---|---|
| **Remove download** (e-reader) | Frees space | Keeps item; can redownload | [Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD) |
| **Permanently delete** (e-reader, online) | Removed | Removed from account | Same |
| **USB sideload** (not Send to Kindle) | File on device | **Not** in cloud; removing from device **permanently deletes** | Same (Note on USB transfers) |
| **Delete via Manage Your Content and Devices** | Removed on next sync | Removed | [Cloud Drive FAQs](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIh9JOMGAKr7bY4zqu) |

Send-to-Kindle EPUBs are **cloud-backed personal documents**, not USB sideloads. “Remove download” is useful to shrink on-device clutter while keeping archives in Amazon’s library; “Permanently delete” is the real cleanup.

### Collections

Collections are **folders for organization**; they do not auto-delete or expire content. Cloud collections can sync across devices when created through supported apps. ([What Are Collections?](https://www.amazon.com/gp/help/customer/display.html?nodeId=T4KX4ALDBNr9flMGqC), [Download Collections to Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GQNG5LCNAE6JYM45))

**Display quirk (community):** The same doc can appear twice in All/Downloaded or inside/outside a collection — one logical file. ([Amazon forum: Duplicate DOCs on Oasis](https://uk.amazonforum.com/s/question/0D54P00006zSmJISA0/duplicate-docs-appearing-in-oasis-library))

Collections could help a user group “BiteSIze” digests manually; BiteSIze cannot push cloud collections through Send to Kindle email alone.

### Storage limits

| Limit type | Documented value | Applies to |
|---|---|---|
| Email attachment total | 50 MB per email (ZIP allowed) | Send to Kindle email | [G7NECT4B4ZWHQ8WV](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV) |
| Web upload | 200 MB per file | Send to Kindle for Web | [200767340](https://www.amazon.com/gp/help/customer/display.html?nodeId=200767340) |
| **Aggregate personal-doc cloud quota** | **Not published** in Customer Service help reviewed | — |
| Amazon Photos free tier | 5 GB photos/videos | **Separate product**, not Kindle personal docs | [How Much Storage do I Have Available?](https://www.amazon.com/gp/help/customer/display.html?nodeId=GC4942XQ5M2T7HGF) |

Amazon forum staff have stated there is **no limit** on personal-document count in the cloud library ([Storage limit in Kindle cloud for personal documents](https://in.amazonforum.com/s/question/0D56Q0000D0MUV0SQO/storage-limit-in-kindle-cloud-for-personal-documents)) — forum, not a guarantee, but aligns with absence of a published cap.

**Device storage** is finite (on-device downloads). Help documents **Remove download** as the space-management action. Exact GB varies by hardware generation; not critical for this note because BiteSIze’s problem is **library clutter**, not device full.

---

## 5. Third-party options — what is actually documented?

| Approach | Deletes from Amazon cloud? | Documented? | ToS / risk |
|---|---|---|---|
| **Calibre “Sharing books by email”** | **No** — sends TO Kindle only | Yes: configure SMTP + approved sender; EPUB instead of MOBI | Legitimate send path; same accumulation problem ([Calibre FAQ](https://manual.calibre-ebook.com/faq.html)) |
| **Calibre device USB** | Removes local copy only unless you also delete in Amazon UI | Send to device docs in GUI | Personal docs on device ≠ cloud delete |
| **Email filters (Gmail, etc.)** | **No** — filters the SMTP **outbox/inbox**, not Amazon’s library | N/A | Harmless but useless for cloud cleanup |
| **Disable Personal Document Archiving** | Stops **new** cloud copies; old ones remain | Amazon help | Prevents future clutter; breaks “read anywhere” cloud backup |
| **Scripts scraping Manage Your Content (FIONA/mycd AJAX, cookie auth)** | Some community tools claim bulk delete | **Not official**; private API | [Conditions of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=508088) prohibits robots/scraping; account risk; fragile |
| **Browser bookmarklet / manual bulk select on amazon.com** | Yes, if user clicks Delete | UI feature, not API | Safe if the human operates the browser |

Calibre’s `--automerge` and duplicate handling apply to **Calibre’s local library database**, not Amazon’s cloud. ([calibredb docs](https://manual.calibre-ebook.com/generated/en/calibredb.html))

**Send to Kindle legal hook:** Using Send to Kindle binds you to Kindle Store Terms of Use; Amazon may “review and remove” distributed content that violates policies — that is **moderation**, not user-controlled retention. ([Kindle Store Terms §2](https://www.amazon.com/gp/help/customer/display.html?nodeId=201014950), [Send to Kindle Legal Information](https://www.amazon.com/gp/help/customer/display.html?nodeId=ThDuDmqnYd2Ouy8c6i))

---

## 6. Practical recommendation for BiteSIze

### What BiteSIze can automate safely

| Idea | Verdict | Rationale |
|---|---|---|
| **Keep unique dated EPUB filenames** (already shipped) | **KEEP** | Avoids accidental same-file confusion; each day is a distinct doc ([§3](#3-resending-the-same-filename--title--replace-or-duplicate)) |
| **Keep SMTP Send to Kindle as best-effort send** | **KEEP** | Official supported ingress ([200767340](https://www.amazon.com/gp/help/customer/display.html?nodeId=200767340)) |
| **Local `output/` retention job** (delete EPUBs older than N days on disk only) | **KEEP (optional)** | BiteSIze-owned files; does not touch Amazon; helps Mac/iCloud disk, not Kindle library |
| **Dashboard reminder / link** (“Clean up old digests in Manage Your Content → Docs”) | **KEEP (docs/UI copy only)** | No Amazon integration; sets user expectation |
| **Disable cloud archiving instructions in README** | **KEEP (docs only)** | Official preference toggle ([G6N7P2TFA2YTH5YW](https://www.amazon.com/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW)); user trade-off: lose cross-device cloud backup |
| **iCloud Books copy** (already optional) | **KEEP** | User-controlled filesystem lifecycle separate from Amazon |

### What the human must do in Amazon’s UI

1. Periodically open [Manage Your Content and Devices](https://www.amazon.com/mycd) → **Content** → filter **Docs**.
2. Select old BiteSIze digests → **Delete** → confirm.
3. **Sync** the Kindle e-reader (or use **Permanently delete** on-device for one-offs). ([Sync Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GDCAMDFMC2LZP6BR), [TIEM9w0fUmk2jXEknD](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD))

Optional habits:

- **Remove download** on the device for read issues still in cloud.
- Manual **Collections** to group digests (organize, not delete).
- **Disable archiving** if the user only wants email-to-device without growing cloud history (understand the trade-off).

### Code ideas — explicit KEEP/DROP for auto-delete in BiteSIze

| Code idea | Decision |
|---|---|
| Amazon login / session cookie store | **DROP** |
| Scrape or call undocumented mycd/FIONA delete AJAX | **DROP** |
| Headless browser to bulk-delete Docs | **DROP** (ToS + brittle) |
| “Delete previous digest via email command” | **DROP** (no such Amazon feature) |
| Resend same filename hoping to replace yesterday | **DROP** (creates duplicates) |
| `kindle.py` post-send DELETE hook | **DROP** |
| Optional local cron: prune `output/*.epub` older than N days | **KEEP** (separate from Kindle; user opt-in) |
| Settings flag `kindle_delivery_enabled` (existing) | **KEEP** |
| User-editable email subject prefix for easier Doc search | **KEEP** (minor UX; optional) |

---

## Sources (primary)

- [Learn About Sending Documents to Your Kindle Library](https://www.amazon.com/gp/help/customer/display.html?nodeId=200767340)
- [Learn How to Use Your Send to Kindle Email Address](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV)
- [Add an Email Address to Receive Documents in Your Kindle Library](https://www.amazon.com/gp/help/customer/display.html?nodeId=GX9XLEVV8G4DB28H)
- [Disable Document Archiving in Your Kindle Library](https://www.amazon.com/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW)
- [Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD)
- [Sync Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GDCAMDFMC2LZP6BR)
- [Send Books to Your Kindle E-Reader Manually (Manage Your Content and Devices)](https://www.amazon.com/gp/help/customer/display.html?nodeId=GGLBJ4VR79NSB26W)
- [What Are Personal Documents?](https://www.amazon.com/gp/help/customer/display.html?nodeId=TFTaJVr74SmBfVs4kD)
- [What Are Collections?](https://www.amazon.com/gp/help/customer/display.html?nodeId=T4KX4ALDBNr9flMGqC)
- [Download Collections to Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GQNG5LCNAE6JYM45)
- [Cloud Drive FAQs (delete imported files at Manage Your Content and Devices)](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIh9JOMGAKr7bY4zqu)
- [Kindle Store Terms of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=201014950)
- [Send to Kindle Legal Information](https://www.amazon.com/gp/help/customer/display.html?nodeId=ThDuDmqnYd2Ouy8c6i)
- [Amazon.com Conditions of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=508088)
- [Amazon Selling Partner API](https://developer.amazonservices.com/)
- [Send to Kindle — Email product page](https://www.amazon.com/sendtokindle/email)
- [Calibre FAQ — email to Kindle](https://manual.calibre-ebook.com/faq.html)

Community (secondary — gaps in official docs):

- [Duplicate Books Through Email Transfer](https://www.amazonforum.com/s/question/0D54P00006zIpIfSAK/duplicate-books-through-email-transfer)
- [Cannot delete personal documents (Docs filter)](https://www.amazonforum.com/s/question/0D54P00006zSzy3SAC/cannot-delete-personal-documents-from-kindledevice-and-cloud)
- [Storage limit in Kindle cloud for personal documents (Amazon forum staff reply)](https://in.amazonforum.com/s/question/0D56Q0000D0MUV0SQO/storage-limit-in-kindle-cloud-for-personal-documents)
