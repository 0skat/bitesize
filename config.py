import os
from pathlib import Path

from rich.console import Console

BASE_DIR     = Path(__file__).parent
SOURCES_FILE = BASE_DIR / "sources.json"
OUTPUT_DIR   = BASE_DIR / "output"

console = Console()

GEMINI_BATCH_SIZE     = 20
GEMINI_TIMEOUT        = 120
GEMINI_CHECK_TIMEOUT  = 6
MAX_ARTICLES_PER_FEED = 10
TRUNCATE_CHARS        = 450

# Drop articles that only have a headline (no RSS body, no trafilatura text, no summary).
MIN_BODY_CHARS    = 180
MIN_SUMMARY_CHARS = 80


def load_env() -> None:
    """Load .env from the project root without overwriting existing env vars."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
