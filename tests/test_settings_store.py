import json

import settings_store as store


def test_init_db_seeds_default_settings(isolated_store):
    store.init_db()
    s = store.load_settings()
    assert s.ai_backend in ("gemini", "ollama", "antigravity")
    assert s.max_articles_per_feed == 10
    assert s.ai_language == "pt-BR"
    assert s.kindle_delivery_enabled is True


def test_set_and_get_setting(isolated_store):
    store.init_db()
    store.set_setting("ai_backend", "ollama")
    assert store.load_settings().ai_backend == "ollama"


def test_migrate_from_sources_json_and_env(isolated_store):
    isolated_store["sources"].write_text(
        json.dumps(
            {
                "categories": {"Tech": {"HN": "https://hnrss.org/frontpage"}},
                "integrations": {"gmail": True, "google_calendar": False},
            }
        )
    )
    isolated_store["env"].write_text(
        "KINDLE_EMAIL=a@kindle.com\nSMTP_USER=u@gmail.com\nAI_BACKEND=ollama\n"
    )
    store.init_db()
    assert store.migrate_from_files_if_empty() is True
    s = store.load_settings()
    assert s.kindle_email == "a@kindle.com"
    assert s.ai_backend == "ollama"
    assert s.integration_gmail is True
    tree = store.load_sources_tree()
    assert tree["Tech"]["HN"] == "https://hnrss.org/frontpage"


def test_sources_crud(isolated_store):
    store.init_db()
    cat_id = store.add_category("Brazil")
    feed_id = store.add_feed(cat_id, "G1", "https://g1.globo.com/rss")
    store.update_feed(feed_id, enabled=False)
    tree = store.load_sources_tree(enabled_only=False)
    assert tree["Brazil"]["G1"] == "https://g1.globo.com/rss"
    assert "G1" not in store.load_sources_tree(enabled_only=True).get("Brazil", {})
    store.delete_feed(feed_id)
    assert "G1" not in store.load_sources_tree(enabled_only=False).get("Brazil", {})
