from unittest.mock import MagicMock, patch

import gemini


def test_process_articles_keeps_missing_batch_ids(monkeypatch):
    articles = [
        {"title": "One", "content": "body one", "source": "A"},
        {"title": "Two", "content": "body two", "source": "B"},
    ]
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini,
        "_call_ai",
        lambda instruction, stdin_data, label="": '[{"id":0,"skip":false,"summary":"Ok.","relevance":70}]',
    )
    out = gemini.process_articles(articles, batch_size=2)
    assert len(out) == 2
    titles = {a["title"] for a in out}
    assert titles == {"One", "Two"}

