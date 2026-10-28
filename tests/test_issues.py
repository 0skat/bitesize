"""Stored issues: recording a run's picks, editing them, and rebuilding."""

from pathlib import Path

import issues


def _art(title, score, **kw):
    base = {
        "title": title,
        "url": f"http://example.test/{title}",
        "source": "Source",
        "summary": f"{title} sentence one. {title} sentence two.",
        "content": "body text " * 40,
        "published": "09:00",
        "tipo": "artigo-completo",
        "temas": ["tecnologia"],
        "relevance": score,
        "relevance_source": "ai",
    }
    base.update(kw)
    return base


def _sections():
    return {
        "Tech": [_art("t1", 90), _art("t2", 85)],
        "Soccer": [_art("s1", 88)],
        "Also considered": [_art("o1", 81)],
    }


def test_record_and_load_round_trip(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections(), "Also considered")
    loaded = issues.load_issue(iid)

    assert loaded["id"] == iid
    assert loaded["epub_name"] == "x.epub"
    assert [s["name"] for s in loaded["sections"]] == ["Tech", "Soccer", "Also considered"]
    assert [s["kind"] for s in loaded["sections"]] == ["main", "main", "overflow"]
    first = loaded["sections"][0]["articles"][0]
    assert first["title"] == "t1"
    assert first["relevance"] == 90
    assert first["temas"] == ["tecnologia"]
    assert first["excluded"] is False


def test_load_issue_omits_bodies_from_the_dashboard_payload(isolated_store):
    """The body is stored for rebuilds but must not bloat the API response."""
    iid = issues.record_issue(Path("output/x.epub"), _sections())
    art = issues.load_issue(iid)["sections"][0]["articles"][0]
    assert "content" not in art


def test_unknown_issue_loads_as_none(isolated_store):
    issues.init_db()
    assert issues.load_issue(999) is None


def test_exclude_marks_only_that_article(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections())
    target = issues.load_issue(iid)["sections"][0]["articles"][0]["id"]

    assert issues.set_excluded(target, True) is True

    sections = issues.load_issue(iid)["sections"]
    flat = [a for s in sections for a in s["articles"]]
    assert [a["excluded"] for a in flat].count(True) == 1
    assert next(a for a in flat if a["id"] == target)["excluded"] is True


def test_exclude_unknown_article_reports_failure(isolated_store):
    issues.init_db()
    assert issues.set_excluded(4242, True) is False


def test_exclude_many_and_restore(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections())
    ids = [a["id"] for s in issues.load_issue(iid)["sections"] for a in s["articles"]]

    assert issues.set_excluded_many(ids, True) == len(ids)
    assert issues.set_excluded_many(ids, False) == len(ids)
    assert issues.set_excluded_many([], True) == 0

    flat = [a for s in issues.load_issue(iid)["sections"] for a in s["articles"]]
    assert all(a["excluded"] is False for a in flat)


def test_sections_for_epub_skips_excluded(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections(), "Also considered")
    loaded = issues.load_issue(iid)
    tech = next(s for s in loaded["sections"] if s["name"] == "Tech")
    issues.set_excluded(tech["articles"][0]["id"], True)

    sections, overflow = issues.issue_sections_for_epub(iid)
    assert [a["title"] for a in sections["Tech"]] == ["t2"]
    assert overflow == "Also considered"
    # Bodies come back, because the EPUB writer renders them.
    assert sections["Tech"][0]["content"]


def test_emptied_section_disappears_rather_than_rendering_blank(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections())
    loaded = issues.load_issue(iid)
    soccer = next(s for s in loaded["sections"] if s["name"] == "Soccer")
    issues.set_excluded(soccer["articles"][0]["id"], True)

    sections, _ = issues.issue_sections_for_epub(iid)
    assert "Soccer" not in sections
    assert "Tech" in sections


def test_list_issues_counts_kept_and_excluded(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections())
    ids = [a["id"] for s in issues.load_issue(iid)["sections"] for a in s["articles"]]
    issues.set_excluded_many(ids[:2], True)

    row = issues.list_issues(10)[0]
    assert row["id"] == iid
    assert row["stored"] == 4
    assert row["excluded"] == 2
    assert row["kept"] == 2
    assert row["epub_exists"] is False  # nothing was actually written


def test_list_issues_is_newest_first(isolated_store):
    a = issues.record_issue(Path("output/a.epub"), {"Tech": [_art("a1", 80)]})
    b = issues.record_issue(Path("output/b.epub"), {"Tech": [_art("b1", 80)]})
    assert [r["id"] for r in issues.list_issues(10)] == [b, a]


def test_delete_issue_removes_its_articles(isolated_store):
    iid = issues.record_issue(Path("output/x.epub"), _sections())
    assert issues.delete_issue(iid) is True
    assert issues.load_issue(iid) is None
    assert issues.list_issues(10) == []
    assert issues.delete_issue(iid) is False


def test_prune_keeps_the_newest_issues(isolated_store):
    made = [
        issues.record_issue(Path(f"output/{i}.epub"), {"Tech": [_art(f"a{i}", 80)]})
        for i in range(5)
    ]
    assert issues.prune_issues(2) == 3
    assert [r["id"] for r in issues.list_issues(10)] == made[-1:-3:-1]
    # Pruned issues take their articles with them.
    assert issues.load_issue(made[0]) is None


def test_prune_zero_keeps_everything(isolated_store):
    for i in range(3):
        issues.record_issue(Path(f"output/{i}.epub"), {"Tech": [_art(f"a{i}", 80)]})
    assert issues.prune_issues(0) == 0
    assert len(issues.list_issues(10)) == 3


def test_record_tolerates_sparse_articles(isolated_store):
    """Gmail and Calendar rows carry fewer fields than an RSS story."""
    iid = issues.record_issue(
        Path("output/x.epub"), {"Calendar": [{"title": "Standup"}]}
    )
    art = issues.load_issue(iid)["sections"][0]["articles"][0]
    assert art["title"] == "Standup"
    assert art["temas"] == []
    assert art["relevance"] == 0


# ── Rebuild ─────────────────────────────────────────────────────────────────


def test_rebuild_writes_an_epub_without_the_excluded(isolated_store, tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "_settings", None)
    out = tmp_path / "issue.epub"
    iid = issues.record_issue(out, _sections(), "Also considered")
    tech = next(s for s in issues.load_issue(iid)["sections"] if s["name"] == "Tech")
    issues.set_excluded(tech["articles"][0]["id"], True)

    result = issues.rebuild_issue(iid, deliver=False)

    assert result["ok"] is True
    assert result["articles"] == 3
    assert out.exists() and out.stat().st_size > 0


def test_rebuild_refuses_when_everything_is_excluded(isolated_store, tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "_settings", None)
    out = tmp_path / "issue.epub"
    iid = issues.record_issue(out, _sections())
    ids = [a["id"] for s in issues.load_issue(iid)["sections"] for a in s["articles"]]
    issues.set_excluded_many(ids, True)

    result = issues.rebuild_issue(iid, deliver=False)
    assert result["ok"] is False
    assert "excluded" in result["error"]
    assert not out.exists()


def test_rebuild_reports_an_unknown_issue(isolated_store):
    issues.init_db()
    result = issues.rebuild_issue(321, deliver=False)
    assert result["ok"] is False
    assert "No stored issue" in result["error"]
