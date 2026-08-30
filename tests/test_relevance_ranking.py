from gemini import (
    CLUSTERED_AI_SCORE_RATIO,
    _fallback_relevance,
    _listwise_cluster_log_line,
    _relevance_from_listwise_rank,
    process_articles,
    spread_tied_scores,
)


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
    assert all(a["relevance_source"] == "fallback" for a in out)


def test_process_articles_sets_relevance_source_ai(monkeypatch):
    import gemini

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini,
        "_call_ai",
        lambda instruction, stdin_data, label="": (
            '[{"id":0,"skip":false,"summary":"One. Two.","relevance":81},'
            '{"id":1,"skip":false,"summary":"Three. Four.","relevance":62}]'
        ),
    )
    articles = [
        {"title": "A", "content": "short", "source": "S"},
        {"title": "B", "content": "longer body", "source": "S"},
    ]
    out = process_articles(articles, batch_size=20)
    assert out[0]["relevance_source"] == "ai"
    assert out[1]["relevance_source"] == "ai"


def test_relevance_from_listwise_rank_spreads_scores():
    scores = [_relevance_from_listwise_rank(r, 5, high=92, low=40) for r in range(1, 6)]
    assert scores == sorted(scores, reverse=True)
    assert min(scores) >= 0
    assert max(scores) <= 100
    assert len(set(scores)) == 5


def test_relevance_from_listwise_rank_uses_batch_score_span():
    scores = [_relevance_from_listwise_rank(r, 3, high=75, low=68) for r in range(1, 4)]
    assert scores == [75, 72, 68]
    assert max(scores) <= 75


def test_process_articles_listwise_remaps_clustered_ai_scores(monkeypatch):
    import gemini

    calls = []

    def fake_call_ai(instruction, stdin_data, label=""):
        calls.append(instruction)
        if "rank" in instruction.lower() or "order" in instruction.lower():
            return '[{"id":1},{"id":0},{"id":2}]'
        return (
            '[{"id":0,"skip":false,"summary":"One. Two.","relevance":72},'
            '{"id":1,"skip":false,"summary":"Three. Four.","relevance":72},'
            '{"id":2,"skip":false,"summary":"Five. Six.","relevance":72}]'
        )

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake_call_ai)

    articles = [
        {"title": "A", "content": "x", "source": "S"},
        {"title": "B", "content": "y", "source": "S"},
        {"title": "C", "content": "z", "source": "S"},
    ]
    out = process_articles(articles, batch_size=20)
    assert len(calls) == 2
    by_title = {a["title"]: a for a in out}
    assert by_title["B"]["relevance"] > by_title["A"]["relevance"]
    assert by_title["A"]["relevance"] > by_title["C"]["relevance"]
    assert all(a["relevance_source"] == "ai" for a in out)


def test_process_articles_skips_listwise_when_scores_are_spread(monkeypatch):
    import gemini

    calls = []

    def fake_call_ai(instruction, stdin_data, label=""):
        calls.append(instruction)
        return (
            '[{"id":0,"skip":false,"summary":"One. Two.","relevance":90},'
            '{"id":1,"skip":false,"summary":"Three. Four.","relevance":55},'
            '{"id":2,"skip":false,"summary":"Five. Six.","relevance":40}]'
        )

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake_call_ai)

    articles = [
        {"title": "A", "content": "x", "source": "S"},
        {"title": "B", "content": "y", "source": "S"},
        {"title": "C", "content": "z", "source": "S"},
    ]
    out = process_articles(articles, batch_size=20)
    assert len(calls) == 1
    scores = sorted([a["relevance"] for a in out], reverse=True)
    assert scores == [90, 55, 40]


def test_clustered_ai_score_ratio_constant():
    assert CLUSTERED_AI_SCORE_RATIO == 0.35


def test_listwise_cluster_log_line_fired():
    arts = [{"relevance": 72}, {"relevance": 72}, {"relevance": 72}]
    line = _listwise_cluster_log_line(arts, order=[1, 0, 2])
    assert "fired" in line
    assert "ratio=" in line


def test_listwise_cluster_log_line_skipped_invalid():
    arts = [{"relevance": 72}, {"relevance": 72}]
    line = _listwise_cluster_log_line(arts, order=None)
    assert "skipped-invalid" in line


def test_listwise_cluster_log_line_skipped_empty():
    arts = [{"relevance": 72}, {"relevance": 72}]
    line = _listwise_cluster_log_line(arts, order=None, empty_response=True)
    assert "skipped-empty" in line


def test_process_articles_listwise_fail_closed_on_invalid_order(monkeypatch):
    import gemini

    def fake_call_ai(instruction, stdin_data, label=""):
        if "rank" in instruction.lower():
            return '[{"id":0},{"id":0},{"id":1}]'
        return (
            '[{"id":0,"skip":false,"summary":"One. Two.","relevance":72},'
            '{"id":1,"skip":false,"summary":"Three. Four.","relevance":72},'
            '{"id":2,"skip":false,"summary":"Five. Six.","relevance":72}]'
        )

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake_call_ai)

    articles = [
        {"title": "A", "content": "x", "source": "S"},
        {"title": "B", "content": "y", "source": "S"},
        {"title": "C", "content": "z", "source": "S"},
    ]
    out = process_articles(articles, batch_size=20)
    assert all(a["relevance_source"] == "ai" for a in out)
    assert max(a["relevance"] for a in out) == 72


def test_process_articles_listwise_leaves_fallback_untouched(monkeypatch):
    import gemini

    def fake_call_ai(instruction, stdin_data, label=""):
        if "rank" in instruction.lower():
            return '[{"id":2},{"id":0},{"id":1}]'
        return (
            '[{"id":0,"skip":false,"summary":"One. Two.","relevance":72},'
            '{"id":1,"skip":false,"summary":"Three. Four.","relevance":72},'
            '{"id":2,"skip":false,"summary":"Five. Six.","relevance":72},'
            '{"id":3,"skip":false,"summary":"Seven. Eight."}]'
        )

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake_call_ai)

    articles = [
        {"title": "AI one", "content": "x", "source": "S"},
        {"title": "AI two", "content": "y", "source": "S"},
        {"title": "AI three", "content": "z", "source": "S"},
        {"title": "Fallback", "content": "x" * 4000, "source": "S", "published_ts": 1},
    ]
    out = process_articles(articles, batch_size=20)
    by_title = {a["title"]: a for a in out}
    fallback_score = by_title["Fallback"]["relevance"]
    assert by_title["Fallback"]["relevance_source"] == "fallback"
    assert by_title["AI three"]["relevance"] > by_title["AI one"]["relevance"]
    assert by_title["Fallback"]["relevance"] == fallback_score
    assert fallback_score < 70


def test_process_articles_listwise_remap_stays_within_batch_span(monkeypatch):
    import gemini

    def fake_call_ai(instruction, stdin_data, label=""):
        if "rank" in instruction.lower():
            return '[{"id":1},{"id":0}]'
        return (
            '[{"id":0,"skip":false,"summary":"One. Two.","relevance":68},'
            '{"id":1,"skip":false,"summary":"Three. Four.","relevance":72}]'
        )

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake_call_ai)

    articles = [
        {"title": "A", "content": "x", "source": "S"},
        {"title": "B", "content": "y", "source": "S"},
    ]
    out = process_articles(articles, batch_size=20)
    by_title = {a["title"]: a for a in out}
    assert max(a["relevance"] for a in out) <= 72
    assert by_title["B"]["relevance"] > by_title["A"]["relevance"]
