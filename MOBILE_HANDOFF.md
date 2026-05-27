# BiteSIze — Mobile Session Handoff

## Resume on your phone

**Open this URL on your phone** (log in with the same Cursor account: `vsalles@simplefractal.com`):

**https://cursor.com/agents#workerId=63943662-35e6-419d-b079-9f6d26381436**

From there you can start a new agent against your Mac (`VIRUS`) with the `bitesize` project loaded.

> **Important:** Your Mac must stay awake and the worker process must keep running. If you close the terminal, restart with:
> ```bash
> cd /Users/victorrodrigues/playground/bitesize
> cursor agent worker start --worker-dir .
> ```

**Tip:** On iPhone, open the URL in Safari → Share → **Add to Home Screen** for a PWA-like app.

Paste this prompt to continue where we left off:
> Read MOBILE_HANDOFF.md and debug Kindle delivery: run `python main.py --all` without `--no-kindle`, fix any SMTP errors, and confirm the EPUB arrives on my Kindle.

---

### Done
- Python app set up (`pip install -r requirements.txt`, `.env` configured)
- Gemini CLI fixed (`gemini_backend.py` uses `-p` flag, not positional prompt)
- EPUB high-priority fixes: paginated indexes (10/page), summary-only blurbs, fallback covers
- Ollama configured (`AI_BACKEND=ollama`, model `gemma4:e4b`)

### Open issue: Kindle email not arriving
You reported the EPUB never showed up on Kindle and no email appeared in Gmail Sent.

**Likely cause:** Recent runs used `--no-kindle`, which skips SMTP entirely:
```bash
python main.py --all --no-kindle   # ← no email sent
```

**To test delivery:**
```bash
cd /Users/victorrodrigues/playground/bitesize
source .venv/bin/activate
python main.py --all
```

**Checklist if it still fails:**
1. `SMTP_USER` (`victorsalles1997@gmail.com`) whitelisted in Amazon → Kindle → Approved Personal Document E-mail List
2. `SMTP_PASSWORD` is a Gmail **App Password** (16 chars, spaces optional)
3. `KINDLE_EMAIL` matches your @kindle.com address exactly
4. Watch terminal for `✓ Sent to Kindle` vs `✗ Kindle delivery failed`

### Key files
| File | Purpose |
|------|---------|
| `main.py` | CLI entry (`--all`, `--no-kindle`) |
| `kindle.py` | SMTP delivery |
| `epub.py` | EPUB generation + layout |
| `.env` | Kindle SMTP + AI backend |
| `output/` | Generated EPUBs |

### Next prompt suggestion (paste on phone)
> Debug Kindle delivery: run `python main.py --all` without `--no-kindle`, fix any SMTP errors, and confirm the EPUB arrives on my Kindle.
