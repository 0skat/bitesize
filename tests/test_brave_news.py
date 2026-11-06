"""Brave Search as an article source.

No test here touches the network: every request is stubbed. What matters is
that results arrive in the same shape the RSS path produces, that dates are
read well enough for the age filter to work on them, and that a paid API
failing never takes the morning run with it.
"""

import time

import pytest

import brave_news


class _Response:
    def __init__(self, payload=None, status=200, raises=None, text="{}"):
        self._payload = payload if payload is not None else {}
        self.status_code = status
        self.ok = 200 <= status < 300
        self._raises = raises
        self.text = text

    def json(self):
        if self._raises:
            raise self._raises
        return self._payload


def _result(**kw):
    base = {
        "title": "A headline",
        "url": "https://www.reuters.com/world/story",
        "description": "Some description text.",
        "page_age": "2026-11-06T09:00:00Z",
        "meta_url": {"netloc": "reuters.com"},
    }
    base.update(kw)
    return base


@pytest.fixture
def stub(monkeypatch):
    """Capture the outgoing request and control the response."""
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        return fake_get.response

    fake_get.response = _Response({"results": [_result()]})
    monkeypatch.setattr(brave_news.requests, "get", fake_get)
    return fake_get, calls


# ── The request ─────────────────────────────────────────────────────────────


def test_the_key_goes_in_the_documented_header(stub):
    _, calls = stub
    brave_news.search_news("test", key="secret-key")
    assert calls[0]["headers"]["X-Subscription-Token"] == "secret-key"
    assert calls[0]["url"] == brave_news.ENDPOINT


def test_freshness_and_count_are_passed_through(stub):
    _, calls = stub
    brave_news.search_news("test", key="k", count=7, freshness="pw")
    assert calls[0]["params"]["freshness"] == "pw"
    assert calls[0]["params"]["count"] == 7
    assert calls[0]["params"]["q"] == "test"


def test_count_is_clamped_to_braves_maximum(stub):
    _, calls = stub
    brave_news.search_news("test", key="k", count=500)
    assert calls[0]["params"]["count"] == brave_news.MAX_COUNT


def test_an_empty_query_makes_no_request(stub):
    _, calls = stub
    assert brave_news.search_news("   ", key="k") == []
    assert calls == []


def test_no_key_makes_no_request(stub, monkeypatch):
    _, calls = stub
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    assert brave_news.search_news("test", key="") == []
    assert calls == []


def test_the_environment_key_wins_over_settings(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "from-env")

    class S:
        brave_api_key = "from-db"

    assert brave_news.api_key(S()) == "from-env"
    monkeypatch.delenv("BRAVE_API_KEY")
    assert brave_news.api_key(S()) == "from-db"


# ── The result shape ────────────────────────────────────────────────────────


def test_a_result_matches_the_rss_article_shape(stub):
    art = brave_news.search_news("test", key="k")[0]
    for field in ("source", "category", "title", "content", "rss_snippet",
                  "url", "published", "published_ts", "summary"):
        assert field in art, field
    assert art["title"] == "A headline"
    assert art["source"] == "reuters.com"
    assert art["rss_snippet"] == art["content"]
    assert art["via"] == "brave"


def test_results_without_a_title_or_url_are_dropped(stub):
    fake, _ = stub
    fake.response = _Response({"results": [
        _result(title=""), _result(url=""), _result(title="Good"),
    ]})
    arts = brave_news.search_news("test", key="k")
    assert [a["title"] for a in arts] == ["Good"]


def test_extra_snippets_are_folded_into_the_text(stub):
    fake, _ = stub
    fake.response = _Response({"results": [
        _result(description="First.", extra_snippets=["Second.", "Third."]),
    ]})
    art = brave_news.search_news("test", key="k")[0]
    assert "First." in art["content"]
    assert "Third." in art["content"]


def test_the_publisher_falls_back_to_the_hostname(stub):
    fake, _ = stub
    fake.response = _Response({"results": [
        _result(meta_url={}, url="https://www.theguardian.com/a/b"),
    ]})
    assert brave_news.search_news("test", key="k")[0]["source"] == "theguardian.com"


# ── Dates, because the age filter depends on them ───────────────────────────


def test_an_iso_page_age_is_read():
    ts = brave_news._timestamp({"page_age": "2026-11-06T09:00:00Z"})
    assert ts > 0
    from datetime import datetime, timezone

    assert datetime.fromtimestamp(ts, timezone.utc).year == 2026


def test_prose_age_is_read_when_there_is_no_timestamp():
    now = time.time()
    ts = brave_news._timestamp({"age": "3 hours ago"}, now=now)
    assert abs((now - ts) - 3 * 3600) < 2


def test_an_unreadable_date_is_zero_not_a_guess():
    """0 means unknown, which the age filter keeps — same as an undated feed."""
    assert brave_news._timestamp({"page_age": "last Tuesday"}) == 0
    assert brave_news._timestamp({}) == 0


def test_an_undated_result_survives_the_age_filter(stub):
    from feed import filter_by_age

    fake, _ = stub
    fake.response = _Response({"results": [_result(page_age="", age="")]})
    arts = brave_news.search_news("test", key="k")
    assert arts[0]["published_ts"] == 0
    kept, dropped = filter_by_age(arts, 1)
    assert len(kept) == 1 and not dropped


def test_a_stale_brave_result_is_dropped_like_any_other(stub):
    """Brave is not exempt from the freshness rules."""
    from feed import filter_by_age

    fake, _ = stub
    old = int(time.time() - 40 * 86400)
    fake.response = _Response({"results": [_result(page_age="", age="40 days ago")]})
    arts = brave_news.search_news("test", key="k")
    assert abs(arts[0]["published_ts"] - old) < 120
    kept, dropped = filter_by_age(arts, 3)
    assert not kept and len(dropped) == 1


# ── Failure never aborts a run ──────────────────────────────────────────────


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_an_http_error_returns_nothing_and_raises_nothing(stub, status):
    fake, _ = stub
    fake.response = _Response({}, status=status)
    assert brave_news.search_news("test", key="k") == []


def test_a_network_error_returns_nothing_and_raises_nothing(stub, monkeypatch):
    def boom(*a, **kw):
        raise brave_news.requests.RequestException("down")

    monkeypatch.setattr(brave_news.requests, "get", boom)
    assert brave_news.search_news("test", key="k") == []


def test_a_non_json_response_returns_nothing(stub):
    fake, _ = stub
    fake.response = _Response(raises=ValueError("not json"))
    assert brave_news.search_news("test", key="k") == []


def test_an_unexpected_payload_returns_nothing(stub):
    fake, _ = stub
    fake.response = _Response({"results": "not a list"})
    assert brave_news.search_news("test", key="k") == []
    fake.response = _Response({"type": "error"})
    assert brave_news.search_news("test", key="k") == []


# ── Query configuration ─────────────────────────────────────────────────────


def test_queries_parse_from_plain_lines():
    raw = """
    # a comment
    Agriculture = farming news
    World = world news site:reuters.com

    nonsense line without an equals
    """
    q = brave_news.parse_queries(raw)
    assert q == {
        "Agriculture": "farming news",
        "World": "world news site:reuters.com",
    }


def test_empty_query_config_is_an_empty_mapping():
    assert brave_news.parse_queries("") == {}
    assert brave_news.parse_queries(None) == {}


def test_fetch_sections_tags_each_article_with_its_section(stub):
    out = brave_news.fetch_sections(
        {"Agriculture": "farming", "Soccer": "liverpool"}, key="k"
    )
    assert set(out) == {"Agriculture", "Soccer"}
    assert out["Agriculture"][0]["category"] == "Agriculture"
    assert out["Soccer"][0]["category"] == "Soccer"


def test_fetch_sections_makes_one_request_per_section(stub):
    _, calls = stub
    brave_news.fetch_sections({"A": "a", "B": "b", "C": "c"}, key="k")
    assert len(calls) == 3


# ── The pipeline ────────────────────────────────────────────────────────────


def test_primary_mode_skips_the_rss_fetch(isolated_store, monkeypatch):
    """"Brave as the main source" must not also fetch every feed."""
    import main
    import settings_store as store

    store.init_db()
    store.set_setting("brave_enabled", "1")
    store.set_setting("brave_mode", "primary")
    store.set_setting("brave_queries", "Tech = technology news")
    settings = store.load_settings()

    fetched = []
    monkeypatch.setattr(main, "fetch_feed",
                        lambda n, u: fetched.append(n) or [])
    monkeypatch.setattr(main.brave_news, "api_key", lambda s=None: "k")
    monkeypatch.setattr(
        main.brave_news, "fetch_sections",
        lambda q, **kw: {"Tech": [{
            "title": "From Brave", "url": "https://x.test/1", "source": "x.test",
            "category": "Tech", "content": "body", "rss_snippet": "body",
            "published": "", "published_ts": int(time.time()), "summary": "",
        }]},
    )
    monkeypatch.setattr(main, "prefilter_by_title", lambda arts, keep: (arts, []))

    out = main.fetch_and_screen({"Tech": {"Some Feed": "http://f.test/rss"}}, settings)
    assert fetched == [], "no RSS feed may be fetched in primary mode"
    assert [a["title"] for a in out] == ["From Brave"]


def test_supplement_mode_fetches_both(isolated_store, monkeypatch):
    import main
    import settings_store as store

    store.init_db()
    store.set_setting("brave_enabled", "1")
    store.set_setting("brave_mode", "supplement")
    store.set_setting("brave_queries", "Tech = technology news")
    settings = store.load_settings()

    monkeypatch.setattr(main, "fetch_feed", lambda n, u: [{
        "title": "From RSS", "url": "https://r.test/1", "source": n,
        "category": "", "content": "body", "rss_snippet": "body",
        "published": "", "published_ts": int(time.time()), "summary": "",
    }])
    monkeypatch.setattr(main.brave_news, "api_key", lambda s=None: "k")
    monkeypatch.setattr(
        main.brave_news, "fetch_sections",
        lambda q, **kw: {"Tech": [{
            "title": "From Brave", "url": "https://x.test/1", "source": "x.test",
            "category": "Tech", "content": "body", "rss_snippet": "body",
            "published": "", "published_ts": int(time.time()), "summary": "",
        }]},
    )
    monkeypatch.setattr(main, "prefilter_by_title", lambda arts, keep: (arts, []))

    out = main.fetch_and_screen({"Tech": {"Some Feed": "http://f.test/rss"}}, settings)
    assert {a["title"] for a in out} == {"From RSS", "From Brave"}


def test_brave_off_makes_no_call(isolated_store, monkeypatch):
    import main
    import settings_store as store

    store.init_db()
    settings = store.load_settings()
    assert settings.brave_enabled is False

    called = []
    monkeypatch.setattr(main.brave_news, "fetch_sections",
                        lambda q, **kw: called.append(1) or {})
    assert main._brave_articles(settings) == {}
    assert called == []


def test_brave_on_but_unconfigured_makes_no_call(isolated_store, monkeypatch):
    """A paid API must not be called with an empty query list or no key."""
    import main
    import settings_store as store

    store.init_db()
    store.set_setting("brave_enabled", "1")
    settings = store.load_settings()

    called = []
    monkeypatch.setattr(main.brave_news, "fetch_sections",
                        lambda q, **kw: called.append(1) or {})
    assert main._brave_articles(settings) == {}   # no queries

    store.set_setting("brave_queries", "Tech = news")
    monkeypatch.setattr(main.brave_news, "api_key", lambda s=None: "")
    assert main._brave_articles(store.load_settings()) == {}   # no key
    assert called == []


def test_brave_queries_is_a_textarea_in_the_dashboard():
    """A text input cannot hold a newline, so a line-per-section setting needs one."""
    import pathlib
    import re

    js = (pathlib.Path(__file__).parent.parent / "dashboard_static" / "app.js"
          ).read_text(encoding="utf-8")
    block = re.search(r"const TEXTAREA_KEYS = new Set\(\[(.*?)\]\);", js, re.S).group(1)
    assert "brave_queries" in block
