"""Claude Code CLI (claude) transport backend."""

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from config import console, get_settings

_CLAUDE_OK: Optional[bool] = None

# Shortcuts and LaunchAgents often omit ~/.local/bin from PATH.
_CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")

# The CLI ships a full coding-agent system prompt and tool catalogue on every
# call. The digest only needs text in, text out, so strip everything strippable:
# this cuts the per-call prompt overhead from ~19k tokens to ~6k.
_LEAN_FLAGS = (
    "--restricted",
    "--strict-mcp-config",
    "--exclude-dynamic-system-prompt-sections",
)

_DISALLOWED_TOOLS = (
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "Task",
    "NotebookEdit",
)

_SYSTEM_PROMPT = (
    "You are a text transformation API. Return only the requested output, "
    "with no preamble, commentary, or markdown fences."
)

# Claude fences JSON even when told not to. Callers parse with
# gemini._extract_json, whose regex fallback tries arrays before objects — so a
# fenced OBJECT containing an array (the section/global cover shape) would yield
# that inner array and be rejected as "Expected dict, got list". Strip the fence
# here so the direct json.loads succeeds and the regex never runs.
_FENCE_RE = re.compile(
    r"\A\s*```(?:json|JSON)?\s*\n(?P<body>.*?)\n?\s*```\s*\Z",
    re.DOTALL,
)


def _strip_code_fence(text: str) -> str:
    """Remove a single wrapping markdown code fence, if present."""
    match = _FENCE_RE.match(text)
    return match.group("body").strip() if match else text


# Every call's token counts are appended here so real usage can be totted up
# after a run instead of estimated. One JSON object per line.
_USAGE_LOG = Path(__file__).parent / "output" / "logs" / "ai-usage.jsonl"


def _record_usage(data: dict, label: str, model: str, elapsed: float) -> None:
    """Append one call's token usage. Never raises — logging must not break a run."""
    try:
        usage = data.get("usage") or {}
        _USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "label": label or "-",
            "model": model,
            "in": usage.get("input_tokens", 0),
            "cache_write": usage.get("cache_creation_input_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "out": usage.get("output_tokens", 0),
            "cost_usd": data.get("total_cost_usd", 0),
            "secs": round(elapsed, 1),
        }
        with _USAGE_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass


def available() -> bool:
    """Return True if the claude CLI is reachable."""
    global _CLAUDE_OK
    if _CLAUDE_OK is None:
        try:
            subprocess.run(
                [_CLAUDE_BIN, "--version"],
                capture_output=True,
                timeout=get_settings().gemini_check_timeout,
            )
            _CLAUDE_OK = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _CLAUDE_OK = False
    return _CLAUDE_OK


def call(instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
    """Run the Claude CLI in print mode and return the response string."""
    tag = f"[{label}] " if label else ""
    settings = get_settings()
    model = (settings.claude_model or "claude-haiku-4-5-20251001").strip()
    timeout = settings.claude_timeout
    prompt = f"{instruction}\n\n{stdin_data}" if stdin_data else instruction

    started = time.monotonic()
    try:
        result = subprocess.run(
            [
                _CLAUDE_BIN,
                "-p",
                prompt,
                "--model",
                model,
                "--output-format",
                "json",
                "--system-prompt",
                _SYSTEM_PROMPT,
                *_LEAN_FLAGS,
                "--disallowed-tools",
                *_DISALLOWED_TOOLS,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        if result.returncode != 0:
            console.print(
                f"  [yellow]⚠  {tag}Claude exited {result.returncode}[/yellow]"
                + (f": {result.stderr.strip()[:200]}" if result.stderr.strip() else "")
            )
            return None

        data = json.loads(result.stdout)
        _record_usage(data, label, model, time.monotonic() - started)
        if data.get("is_error") or data.get("subtype") != "success":
            console.print(
                f"  [yellow]⚠  {tag}Claude returned "
                f"{data.get('subtype')!r} (error={data.get('is_error')})[/yellow]"
            )
            return None
        response = data.get("result", "")
        if not isinstance(response, str):
            return None
        return _strip_code_fence(response.strip())

    except subprocess.TimeoutExpired:
        console.print(f"  [yellow]⚠  {tag}Claude call timed out ({timeout}s)[/yellow]")
    except json.JSONDecodeError as e:
        console.print(f"  [yellow]⚠  {tag}Claude JSON decode failed: {e}[/yellow]")
    except FileNotFoundError:
        console.print("  [yellow]⚠  Claude CLI (claude) not found[/yellow]")
    return None
