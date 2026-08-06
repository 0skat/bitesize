"""Ollama HTTP transport backend."""
import json
import socket
import urllib.error
import urllib.request
from typing import Optional

from config import console, get_settings

_SYSTEM_PREFIX = (
    "You are a JSON-only assistant. You NEVER output prose, markdown, or explanation.\n"
    "Every response is a single valid JSON object or array and nothing else.\n"
    "Do not include ```json fences. Do not explain your reasoning. Output JSON only."
)


def available() -> bool:
    """Return True if Ollama is running and reachable."""
    try:
        s = get_settings()
        url = f"http://{s.ollama_host}/api/tags"
        urllib.request.urlopen(url, timeout=s.gemini_check_timeout)
        return True
    except Exception:
        return False


def call(instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
    """Call Ollama and return the model's response string, or None on failure."""
    tag = f"[{label}] " if label else ""
    s = get_settings()
    payload = json.dumps({
        "model": s.ollama_model,
        "prompt": f"{_SYSTEM_PREFIX}\n\n{instruction}\n\n{stdin_data}",
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"http://{s.ollama_host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=s.ollama_timeout) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            return data.get("response", "")
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, TimeoutError) as e:
            console.print(f"  [yellow]⚠  {tag}Ollama request failed: {e}[/yellow]")
            return None
        except json.JSONDecodeError as e:
            if attempt == 0:
                console.print(f"  [yellow]⚠  {tag}Ollama JSON decode failed, retrying: {e}[/yellow]")
                continue
            console.print(f"  [yellow]⚠  {tag}Ollama JSON decode failed after retry: {e}[/yellow]")
            return None

    return None
