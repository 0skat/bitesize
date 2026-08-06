from datetime import datetime

import config
import settings_store as store
from ai_locale import (
    ai_language_code,
    ai_output_language_rule,
    epub_label,
    format_digest_date,
)
from settings_store import Settings


def test_default_ai_language_is_brazilian_portuguese():
    assert Settings().ai_language == "pt-BR"


def test_ai_output_language_rule_pt_br(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "pt-BR")
    monkeypatch.setattr(config, "_settings", None)

    rule = ai_output_language_rule()
    assert "Brazilian Portuguese" in rule
    assert "pt-BR" in rule


def test_epub_labels_portuguese(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "pt-BR")
    monkeypatch.setattr(config, "_settings", None)

    assert epub_label("summary") == "Resumo"
    assert ai_language_code() == "pt-BR"


def test_format_digest_date_portuguese(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "pt-BR")
    monkeypatch.setattr(config, "_settings", None)

    text = format_digest_date(datetime(2026, 8, 5, 9, 0))
    assert "agosto" in text
    assert "2026" in text
