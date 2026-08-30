from unittest.mock import patch

import gemini
from ai_locale import epub_label, format_tag_line
from epub import _article_body_html
from tags import TEMAS, TIPOS, infer_tipo, normalize_tags


LONG_BODY = (
    "O governo anunciou hoje uma série de medidas econômicas que devem "
    "impactar o mercado nos próximos trimestres. Analistas ouvidos pela "
    "reportagem avaliam que a combinação de cortes de gastos e incentivos "
    "fiscais pode reduzir a inflação sem comprometer o crescimento do PIB. "
    "A decisão foi tomada após reunião extraordinária do comitê de política."
)


def test_infer_tipo_short_body_is_resumo():
    art = {"title": "Notícia curta", "content": "Apenas um parágrafo breve."}
    assert infer_tipo(art) == "resumo"


def test_infer_tipo_subscribe_language_is_resumo():
    art = {
        "title": "Matéria premium",
        "content": LONG_BODY + " Assine para continuar lendo o restante.",
    }
    assert infer_tipo(art) == "resumo"


def test_infer_tipo_title_snippet_is_resumo():
    art = {
        "title": "Economia cresce no terceiro trimestre",
        "content": "Economia cresce no terceiro trimestre",
    }
    assert infer_tipo(art) == "resumo"


def test_infer_tipo_rss_snippet_echo_is_resumo():
    rss = (
        "O Banco Central manteve a taxa Selic em 10,75% ao ano na reunião desta "
        "quarta-feira. A decisão era esperada pelo mercado e reflete o cenário "
        "de inflação ainda acima da meta estabelecida pelo Conselho Monetário."
    )
    art = {
        "title": "BC mantém Selic",
        "content": rss,
        "rss_snippet": rss,
    }
    assert infer_tipo(art) == "resumo"


def test_normalize_tags_deduplicates_temas():
    art = {"title": "T", "content": "Short"}
    normalize_tags(
        art,
        {"tipo": "resumo", "temas": ["política", "economia", "política", "economia"]},
    )
    assert art["temas"] == ["política", "economia"]


def test_infer_tipo_long_unique_body_is_artigo_completo():
    art = {"title": "Análise econômica", "content": LONG_BODY}
    assert infer_tipo(art) == "artigo-completo"


def test_normalize_tags_drops_unknown_tema():
    art = {"title": "T", "content": "Short"}
    normalize_tags(art, {"tipo": "resumo", "temas": ["política", "sports", "tecnologia"]})
    assert art["tipo"] == "resumo"
    assert art["temas"] == ["política", "tecnologia"]


def test_normalize_tags_invalid_tipo_falls_back_to_heuristic():
    art = {"title": "Análise", "content": LONG_BODY}
    normalize_tags(art, {"tipo": "full-article", "temas": ["economia"]})
    assert art["tipo"] == "artigo-completo"
    assert art["temas"] == ["economia"]


def test_tipos_and_temas_vocabularies():
    assert TIPOS == {"resumo", "artigo-completo"}
    assert "política" in TEMAS
    assert "sports" not in TEMAS


def test_process_articles_stores_tags_from_ai_batch(monkeypatch):
    articles = [
        {"title": "One", "content": LONG_BODY, "source": "A"},
    ]
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini,
        "_call_ai",
        lambda instruction, stdin_data, label="": (
            '[{"id":0,"skip":false,"summary":"Ok.","relevance":70,'
            '"tipo":"artigo-completo","temas":["política","brasil"]}]'
        ),
    )
    out = gemini.process_articles(articles, batch_size=1)
    assert len(out) == 1
    assert out[0]["tipo"] == "artigo-completo"
    assert out[0]["temas"] == ["política", "brasil"]


def test_process_articles_heuristic_tags_when_ai_off(monkeypatch):
    articles = [{"title": "T", "content": "Teaser only.", "source": "A"}]
    monkeypatch.setattr(gemini, "_ai_available", lambda: False)
    out = gemini.process_articles(articles, batch_size=1)
    assert len(out) == 1
    assert out[0]["tipo"] == "resumo"
    assert out[0]["temas"] == []


def test_format_tag_line_pt_br(isolated_store, monkeypatch):
    import config
    import settings_store as store

    store.init_db()
    store.set_setting("ai_language", "pt-BR")
    monkeypatch.setattr(config, "_settings", None)

    line = format_tag_line("artigo-completo", ["política", "economia"])
    assert "Artigo completo" in line
    assert "política" in line
    assert "economia" in line


def test_epub_includes_tag_line(isolated_store, monkeypatch):
    import config
    import settings_store as store

    store.init_db()
    store.set_setting("ai_language", "pt-BR")
    monkeypatch.setattr(config, "_settings", None)

    art = {
        "title": "Story",
        "content": LONG_BODY,
        "summary": "Resumo em duas frases.",
        "relevance": 72,
        "tipo": "artigo-completo",
        "temas": ["política"],
    }
    html = _article_body_html(art)
    assert "Artigo completo" in html
    assert "política" in html


def test_epub_tag_line_without_summary(isolated_store, monkeypatch):
    import config
    import settings_store as store

    store.init_db()
    store.set_setting("ai_language", "pt-BR")
    monkeypatch.setattr(config, "_settings", None)

    art = {
        "title": "Story",
        "content": "Teaser only.",
        "summary": "",
        "relevance": 50,
        "tipo": "resumo",
        "temas": ["economia"],
    }
    html = _article_body_html(art)
    assert "Resumo" in html
    assert "economia" in html
    assert "summary-label" not in html
    assert epub_label("relevance_score") not in html
