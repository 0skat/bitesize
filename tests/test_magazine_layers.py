from magazine_layers import (
    cover_teasers,
    is_same_story,
    ranked_excluding_hero,
)


def test_is_same_story_by_title():
    a = {"title": "Lula lidera segundo turno", "url": "https://a.com/1"}
    b = {"title": "Lula lidera segundo turno", "url": "https://b.com/2"}
    assert is_same_story(a, b) is True


def test_cover_teasers_skip_hero():
    hero = {"title": "Hero story", "url": "https://x.com/h", "source": "G1"}
    sections = {
        "Brazil": [
            hero,
            {"title": "Copom mantém Selic", "url": "https://x.com/2", "source": "Folha"},
        ],
        "Tech": [
            {"title": "Google AI exodus", "url": "https://x.com/3", "source": "Verge"},
        ],
    }
    teasers = cover_teasers(sections, hero)
    assert len(teasers) == 2
    assert all("Hero story" not in t for t in teasers)
    assert "Brazil · Folha" in teasers[0]
    assert "Tech · Verge" in teasers[1]


def test_ranked_excluding_hero():
    hero = {"title": "Hero", "url": "https://h", "relevance": 99}
    sections = {
        "Brazil": [
            hero,
            {"title": "Second", "url": "https://s", "relevance": 80},
        ],
    }
    ranked = ranked_excluding_hero(sections, hero, limit=5)
    assert len(ranked) == 1
    assert ranked[0][2]["title"] == "Second"
