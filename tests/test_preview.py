from preview import build_source_preview


def test_preview_lists_headlines_per_feed():
    sources = {
        "categories": [
            {
                "id": 1,
                "name": "Brazil",
                "feeds": [
                    {
                        "id": 10,
                        "name": "Veja",
                        "url": "https://veja.abril.com.br/feed/",
                        "enabled": True,
                    }
                ],
            }
        ]
    }

    def fake_fetch(name, url, max_articles=None):
        assert name == "Veja"
        assert max_articles == 5
        return [
            {"title": "Story A", "url": "https://veja.example/a", "published": "08:00"},
            {"title": "Story B", "url": "https://veja.example/b", "published": "07:30"},
        ]

    out = build_source_preview(sources, fetch_fn=fake_fetch, max_headlines=5)
    feed = out["categories"][0]["feeds"][0]
    assert feed["name"] == "Veja"
    assert feed["enabled"] is True
    assert [h["title"] for h in feed["headlines"]] == ["Story A", "Story B"]


def test_preview_keeps_disabled_feeds_and_records_fetch_errors():
    sources = {
        "categories": [
            {
                "id": 1,
                "name": "World",
                "feeds": [
                    {
                        "id": 2,
                        "name": "AP News",
                        "url": "https://apnews.example/rss",
                        "enabled": False,
                    }
                ],
            }
        ]
    }

    def fake_fetch(name, url, max_articles=None):
        raise RuntimeError("403 Forbidden")

    out = build_source_preview(sources, fetch_fn=fake_fetch, max_headlines=3)
    feed = out["categories"][0]["feeds"][0]
    assert feed["enabled"] is False
    assert feed["headlines"] == []
    assert "403" in feed["error"]
