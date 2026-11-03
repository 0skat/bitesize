"""Choosing which interface the dashboard listens on.

Binding beyond loopback is the moment the password stops being optional, so
the decision lives in one place with the safety check attached to it.
"""

from __future__ import annotations

import ipaddress
import socket
import subprocess

# Tailscale hands every node an address in the 100.64.0.0/10 CGNAT range.
_TAILNET = ipaddress.ip_network("100.64.0.0/10")


def tailscale_address() -> str | None:
    """This machine's tailnet IPv4 address, or None if it is not connected."""
    try:
        out = subprocess.run(
            ["/sbin/ifconfig"], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None

    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("inet "):
            continue
        candidate = line.split()[1]
        try:
            if ipaddress.ip_address(candidate) in _TAILNET:
                return candidate
        except ValueError:
            continue
    return None


def is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.strip().lower() in {"localhost", ""}


def resolve_host(configured: str) -> tuple[str, str | None]:
    """Turn the setting into an address to bind. Returns (host, problem).

    `problem` is a message when the request cannot be honoured, in which case
    the caller should fall back to loopback rather than guess.
    """
    want = (configured or "127.0.0.1").strip()

    if want.lower() == "tailscale":
        addr = tailscale_address()
        if addr is None:
            return "127.0.0.1", (
                "dashboard_host=tailscale but no tailnet address was found — "
                "is Tailscale connected? Falling back to 127.0.0.1."
            )
        return addr, None

    if want == "0.0.0.0":
        return want, None

    try:
        socket.inet_aton(want)
    except OSError:
        if not is_loopback(want):
            return "127.0.0.1", (
                f"dashboard_host={want!r} is not an address this machine can "
                "bind. Falling back to 127.0.0.1."
            )
    return want, None
