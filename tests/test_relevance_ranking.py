from gemini import _fallback_relevance, process_articles, spread_tied_scores


def test_fallback_relevance_does_not_use_three_fixed_buckets():
    short = _fallback_relevance({"content": "x" * 200})
    mid = _fallback_relevance({"content": "x" * 2200})
    long = _fallback_relevance({"content": "x" * 4000})
    longer = _fallback_relevance({"content": "x" * 8000})
    assert len({short, mid, long, longer}) >= 3
    assert long != 78
    assert mid != 70
    assert max(short, mid, long, longer) < 70


def test_spread_tied_scores_breaks_identical_relevance():
    articles = [
        {"title": "Zebra", "relevance": 78, "published_ts": 100},
        {"title": "Alpha", "relevance": 78, "published_ts": 300},
        {"title": "Mid", "relevance": 70, "published_ts": 200},
    ]
    out = spread_tied_scores(articles)
    scores = [a["relevance"] for a in out]
    assert scores[0] != scores[1]
    assert max(scores[0], scores[1]) > scores[2]
    newest = next(a for a in out if a["title"] == "Alpha")
    oldest = next(a for a in out if a["title"] == "Zebra")
    assert newest["relevance"] > oldest["relevance"]


def test_process_articles_uses_spread_when_ai_omits_scores(monkeypatch):
    import gemini

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini,
        "_call_ai",
        lambda instruction, stdin_data, label="": (
            '[{"id":0,"skip":false,"summary":"One. Two."},'
            '{"id":1,"skip":false,"summary":"Three. Four."}]'
        ),
    )
    articles = [
        {"title": "A", "content": "x" * 4000, "source": "S", "published_ts": 2},
        {"title": "B", "content": "x" * 4000, "source": "S", "published_ts": 1},
    ]
    out = process_articles(articles, batch_size=20)
    assert out[0]["relevance"] != out[1]["relevance"]
