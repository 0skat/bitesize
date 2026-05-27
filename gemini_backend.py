"""Gemini CLI transport backend."""
import json
import subprocess
from typing import Optional

from config import console, GEMINI_TIMEOUT, GEMINI_CHECK_TIMEOUT

_GEMINI_OK: Optional[bool] = None


def available() -> bool:
    """Return True if the gemini CLI is reachable."""
    global _GEMINI_OK
    if _GEMINI_OK is None:
        try:
            subprocess.run(
                ["gemini", "--version"],
                capture_output=True,
                timeout=GEMINI_CHECK_TIMEOUT,
            )
            _GEMINI_OK = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _GEMINI_OK = False
    return _GEMINI_OK


def call(instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
    """Run Gemini CLI and return the response string, or None on failure."""
    tag = f"[{label}] " if label else ""
    try:
        result = subprocess.run(
            ["gemini", "--output-format", "json", "-p", instruction],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=GEMINI_TIMEOUT,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("response", "")
        else:
            console.print(
                f"  [yellow]⚠  {tag}Gemini exited {result.returncode}[/yellow]"
                + (f": {result.stderr.strip()[:200]}" if result.stderr.strip() else "")
            )
    except subprocess.TimeoutExpired:
        console.print(f"  [yellow]⚠  {tag}Gemini call timed out ({GEMINI_TIMEOUT}s)[/yellow]")
    except json.JSONDecodeError as e:
        console.print(f"  [yellow]⚠  {tag}Gemini outer JSON decode failed: {e}[/yellow]")
    except FileNotFoundError:
        console.print("  [yellow]⚠  Gemini CLI not found[/yellow]")
    return None
