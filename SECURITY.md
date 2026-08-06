# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| main    | yes       |

## Threat model

BiteSIze is a **single-user local application**. The dashboard listens on `127.0.0.1` only.
Users supply their own RSS feeds, SMTP credentials, and AI backend keys.

## Reporting a vulnerability

Open a [private GitHub security advisory](https://github.com/security/advisories/new) on this repository.
Do not open public issues for undisclosed vulnerabilities.

## Known sensitive surfaces

- `data/bitesize.db` stores SMTP passwords — never commit this file.
- Dashboard write APIs require `DASHBOARD_TOKEN` when set.
- Wordflow `/api/chat` is localhost-only unless `ALLOW_PUBLIC_CHAT=1`.
- RSS feed URLs are fetched as the local user — only add feeds you trust.
