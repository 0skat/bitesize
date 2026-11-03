# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| main    | yes       |

## Threat model

BiteSIze is a **single-user local application**. The dashboard listens on `127.0.0.1` only, and nothing in it is designed to face the public internet. Users supply their own RSS feeds, SMTP credentials, and AI backend keys.

### Two access models

Which one is active depends on whether a dashboard password is set.

**No password (default).** The loopback bind is the security boundary. `GET` routes are open to anything that can reach the port; writes need the bearer token in `data/dashboard.token`. Fine on a machine you alone use, and only on loopback.

**Password set** (`./run.sh set-password`). Every `/api/` route requires a session cookie or the bearer token, **reads included**. Static files stay open so the login page can load.

The second model exists because the first one silently stops holding the moment the dashboard is reached through a proxy. `tailscale serve` terminates TLS on the tailnet and forwards to `127.0.0.1`, so every request arrives from loopback and "local means trusted" would hand settings — SMTP password included, albeit masked — to anything on the tailnet. **Set a password before exposing the dashboard by any means.**

Passwords are stored as an scrypt hash (n=2^15, r=8, 16-byte random salt per password) in `data/dashboard_auth.json`, mode `0600`. Verification is constant-time. The plaintext is never written. Session cookies are signed with a persisted 32-byte key in `data/dashboard_secret`, also `0600`, and are `HttpOnly` with `SameSite=Lax`; set `dashboard_cookie_secure` once you only ever reach the dashboard over HTTPS. Failed logins are throttled to ten per five minutes per source address.

### What is still not covered

- There is **no TLS in the application**. Over a tunnel, the tunnel provides it; over a `dashboard_host=tailscale` bind, WireGuard does. Do not put this on a LAN or the internet in plaintext.
- `dashboard_host` refuses any non-loopback bind while no password is set, and falls back to `127.0.0.1` with a message. That interlock is the only thing standing between a mistyped setting and open reads, so do not remove it.
- There is **one** account and no roles. Anyone with the password or the token has full control, including triggering AI spend.
- The bearer token never expires and is not rotated; delete `data/dashboard.token` to roll it.

## Reporting a vulnerability

Open a [private GitHub security advisory](https://github.com/victor-salles/bitesize/security/advisories/new) on this repository.
Do not open public issues for undisclosed vulnerabilities.

## Known sensitive surfaces

- `data/bitesize.db` stores SMTP passwords — never commit this file.
- Dashboard write APIs require `DASHBOARD_TOKEN` when set; with a password set, reads require credentials too.
- `data/dashboard_auth.json` and `data/dashboard_secret` hold the password hash and the cookie-signing key — both `0600`, both inside the gitignored `data/`.
- Wordflow `/api/chat` is localhost-only unless `ALLOW_PUBLIC_CHAT=1`.
- RSS feed URLs are fetched as the local user — only add feeds you trust.
