import os
from pathlib import Path

from rich.console import Console

import settings_store
from settings_store import Settings

BASE_DIR = Path(__file__).parent
SOURCES_FILE = BASE_DIR / "sources.json"
OUTPUT_DIR = BASE_DIR / "output"

console = Console()

_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        settings_store.init_db()
        settings_store.migrate_from_files_if_empty()
        _settings = settings_store.load_settings()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = None
    return get_settings()


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
