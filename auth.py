"""Password authentication for the dashboard.

The dashboard used to rely on its `127.0.0.1` bind for secrecy and a bearer
token for writes. That stops working the moment it is reached through a
tunnel: `tailscale serve` proxies from the tailnet to loopback, so every
request *looks* local and "loopback is trusted" would hand settings to anyone
on the tailnet. A password closes that, and is far easier to use from a tablet
than pasting a token into every browser.

Only the standard library is used. The password is never stored, only an
scrypt hash of it, in a file readable by its owner alone.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from config import BASE_DIR

AUTH_FILE = BASE_DIR / "data" / "dashboard_auth.json"
SECRET_FILE = BASE_DIR / "data" / "dashboard_secret"

# scrypt parameters. n=2**15 with r=8 costs about 32MB and a tenth of a second
# per attempt, which is irrelevant for a human login and expensive for a
# brute-force attempt against a stolen hash.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 64
_SALT_BYTES = 16

MIN_PASSWORD_LENGTH = 8


def _write_private(path: Path, text: str) -> None:
    """Write a file only its owner can read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with restrictive permissions rather than fixing them afterwards,
    # so the contents are never briefly world-readable.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        handle = os.fdopen(fd, "w", encoding="utf-8")
    except Exception:
        os.close(fd)
        raise
    with handle as fh:          # fdopen now owns the descriptor
        fh.write(text)
    # An existing file keeps its old mode through O_CREAT, so set it explicitly.
    os.chmod(path, 0o600)


def _derive(password: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    # OpenSSL caps scrypt memory at 32MB by default, and these parameters need
    # exactly 128*n*r — 32MB — plus overhead, so the cap has to be raised or
    # the call fails with "memory limit exceeded".
    maxmem = 128 * n * r * 2
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=_DKLEN,
        maxmem=maxmem,
    )


def password_is_set() -> bool:
    """True when a dashboard password has been configured."""
    if not AUTH_FILE.exists():
        return False
    try:
        data = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("hash") and data.get("salt"))


def set_password(password: str) -> None:
    """Store a new password hash. Raises ValueError on a weak password."""
    password = (password or "").strip()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _derive(password, salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    _write_private(
        AUTH_FILE,
        json.dumps(
            {
                "algo": "scrypt",
                "n": _SCRYPT_N,
                "r": _SCRYPT_R,
                "p": _SCRYPT_P,
                "salt": salt.hex(),
                "hash": digest.hex(),
            },
            indent=2,
        )
        + "\n",
    )


def clear_password() -> bool:
    """Remove the password. Returns True if one was there to remove."""
    if AUTH_FILE.exists():
        AUTH_FILE.unlink()
        return True
    return False


def verify_password(password: str) -> bool:
    """Constant-time check against the stored hash."""
    if not password:
        return False
    try:
        data: dict[str, Any] = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    try:
        salt = bytes.fromhex(data["salt"])
        expected = bytes.fromhex(data["hash"])
        n = int(data.get("n", _SCRYPT_N))
        r = int(data.get("r", _SCRYPT_R))
        p = int(data.get("p", _SCRYPT_P))
    except (KeyError, ValueError, TypeError):
        return False

    try:
        candidate = _derive(password, salt, n=n, r=r, p=p)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, expected)


def session_secret() -> bytes:
    """Key for signing session cookies, generated once and persisted.

    Kept out of the settings database so it is never served by the settings
    API, and regenerated only if the file is deleted — which simply logs
    everyone out.
    """
    if SECRET_FILE.exists():
        raw = SECRET_FILE.read_text(encoding="utf-8").strip()
        if raw:
            try:
                return bytes.fromhex(raw)
            except ValueError:
                pass
    secret = secrets.token_bytes(32)
    _write_private(SECRET_FILE, secret.hex() + "\n")
    return secret
