import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    import settings_store as store

    db = tmp_path / "bitesize.db"
    sources = tmp_path / "sources.json"
    env = tmp_path / ".env"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "SOURCES_FILE", sources)
    monkeypatch.setattr(store, "ENV_FILE", env)
    return {"db": db, "sources": sources, "env": env}
