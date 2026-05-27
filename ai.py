"""
AI transport router.

Reads AI_BACKEND from config and delegates call() / available()
to the appropriate backend. Callers only import from here.
"""
from config import AI_BACKEND

if AI_BACKEND == "ollama":
    from ollama_backend import call, available
else:
    from gemini_backend import call, available

__all__ = ["call", "available"]
