"""
AI transport router.

Reads ai_backend from settings and delegates call() / available()
to the appropriate backend. Callers only import from here.
"""

from typing import Optional

from config import get_settings


def available() -> bool:
    backend = get_settings().ai_backend
    if backend == "ollama":
        from ollama_backend import available as _available
    elif backend == "antigravity":
        from antigravity_backend import available as _available
    elif backend == "claude":
        from claude_backend import available as _available
    else:
        from gemini_backend import available as _available
    return _available()


def call(instruction: str, stdin_data: str, label: str = "") -> Optional[str]:
    backend = get_settings().ai_backend
    if backend == "ollama":
        from ollama_backend import call as _call
    elif backend == "antigravity":
        from antigravity_backend import call as _call
    elif backend == "claude":
        from claude_backend import call as _call
    else:
        from gemini_backend import call as _call
    return _call(instruction, stdin_data, label)


__all__ = ["call", "available"]
