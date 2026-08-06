"""Google Antigravity CLI (agy) transport backend."""

import json
import subprocess
from typing import Optional

from config import console, get_settings

_AGY_OK: Optional[bool] = None


def available() -> bool:
    """Return True if the agy CLI is reachable."""
    global _AGY_OK
    if _AGY_OK is None:
        try:
            subprocess.run(
                ["agy", "--version"],
                capture_output=True,
                timeout=get_settings().gemini_check_timeout,
            )
            _AGY_OK = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _AGY_OK = False
    return _AGY_OK


def call(instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
    """Run Antigravity CLI in print mode and return the response string."""
    tag = f"[{label}] " if label else ""
    settings = get_settings()
    model = (settings.antigravity_model or "gemini-3.5-flash-high").strip()
    timeout = settings.gemini_timeout
    prompt = f"{instruction}\n\n{stdin_data}" if stdin_data else instruction

    try:
        result = subprocess.run(
            [
                "agy",
                f"--model={model}",
                "--output-format",
                "json",
                "--disable-slash-commands",
                "--dangerously-skip-permissions",
                "-p",
                prompt,
                "--print-timeout",
                f"{timeout}s",
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if result.returncode != 0:
            console.print(
                f"  [yellow]⚠  {tag}Antigravity exited {result.returncode}[/yellow]"
                + (f": {result.stderr.strip()[:200]}" if result.stderr.strip() else "")
            )
            return None

        data = json.loads(result.stdout)
        if data.get("status") != "SUCCESS":
            console.print(
                f"  [yellow]⚠  {tag}Antigravity status {data.get('status')!r}[/yellow]"
            )
            return None
        response = data.get("response", "")
        return response.strip() if isinstance(response, str) else None

    except subprocess.TimeoutExpired:
        console.print(
            f"  [yellow]⚠  {tag}Antigravity call timed out ({timeout}s)[/yellow]"
        )
    except json.JSONDecodeError as e:
        console.print(f"  [yellow]⚠  {tag}Antigravity JSON decode failed: {e}[/yellow]")
    except FileNotFoundError:
        console.print("  [yellow]⚠  Antigravity CLI (agy) not found[/yellow]")
    return None
