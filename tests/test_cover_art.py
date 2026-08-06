from cover_art import COVER_HEIGHT, COVER_WIDTH, render_magazine_cover


def test_render_magazine_cover_returns_jpeg():
    data = render_magazine_cover(
        masthead="Resumo de Notícias",
        headline="Crise climática redefine política na América Latina",
        edition_line="quarta-feira, 5 de agosto de 2026 · 42 artigos",
        teasers=["Brazil · Folha · Reforma avança", "Tech · Verge · IA em foco"],
        teasers_label="Também nesta edição",
    )
    assert data[:2] == b"\xff\xd8"
    assert len(data) > 10_000


def test_cover_dimensions():
    assert COVER_WIDTH == 1600
    assert COVER_HEIGHT == 2560
    assert round(COVER_HEIGHT / COVER_WIDTH, 1) == 1.6
