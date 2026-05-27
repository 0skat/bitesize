import os
from pathlib import Path

from rich.console import Console

BASE_DIR = Path(__file__).parent
SOURCES_FILE = BASE_DIR / "sources.json"
OUTPUT_DIR = BASE_DIR / "output"

console = Console()

GEMINI_BATCH_SIZE = 20
GEMINI_TIMEOUT = 120
GEMINI_CHECK_TIMEOUT = 6
MAX_ARTICLES_PER_FEED = 10
TRUNCATE_CHARS = 450
FEED_TIMEOUT = 15
USER_AGENT = "BiteSIze/1.0 (+https://github.com/local/bitesize)"

# Drop articles that only have a headline (no RSS body, no trafilatura text, or no summary).
MIN_BODY_CHARS = 180
MIN_SUMMARY_CHARS = 80

INDEX_ENTRIES_PER_PAGE = 10
# Highest-scoring stories listed on the global digest cover (after sorting by relevance).
TOP_PICKS_ON_COVER = 6

GMAIL_MAX_THREADS = int(os.getenv("GMAIL_MAX_THREADS", "30"))
GMAIL_LOOKBACK_HOURS = int(os.getenv("GMAIL_LOOKBACK_HOURS", "24"))

CALENDAR_LOOKAHEAD_DAYS = int(os.getenv("CALENDAR_LOOKAHEAD_DAYS", "7"))
CALENDAR_LOOKBACK_DAYS = int(os.getenv("CALENDAR_LOOKBACK_DAYS", "3"))

AI_BACKEND = os.getenv("AI_BACKEND", "gemini")  # "gemini" | "ollama"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))


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
