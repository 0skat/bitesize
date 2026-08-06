# Wordflow (experimental)

Local-only by default. `/api/chat` rejects non-localhost hosts unless `ALLOW_PUBLIC_CHAT=1`.

Never deploy without authentication if exposing beyond your machine.

## Setup

```bash
cd wordflow
npm install
cp .env.local.example .env.local   # add ANTHROPIC_API_KEY
npm run dev
```

Open http://localhost:3000
