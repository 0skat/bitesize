"""Language settings for AI-generated text and EPUB labels."""

from __future__ import annotations

from datetime import datetime

from config import get_settings

LANGUAGE_LABELS: dict[str, str] = {
    "pt-BR": "Brazilian Portuguese",
    "en": "English",
    "es": "Spanish",
}

EPUB_LABELS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "digest_title": "Resumo de Notícias",
        "summary": "Resumo",
        "relevance_score": "Pontuação de relevância",
        "relevance": "Relevância",
        "top_stories": "Principais histórias por relevância",
        "score": "nota",
        "articles": "artigos",
        "article_of": "de",
        "read_full": "Ler artigo completo online →",
        "contents": "Índice",
        "sections_today": "Suas seções nesta edição.",
        "edition_overview": "Nesta edição",
        "also_inside": "Também nesta edição",
        "by_section": "Por editoria",
        "fallback_section_editorial": "{count} histórias em {category} hoje.",
        "fallback_section_lead": "Destaque:",
        "fallback_global_headline": "Resumo de hoje",
        "fallback_global_editorial": (
            "Este resumo cobre {total} histórias em {sections} seções."
        ),
        "tipo_resumo": "Resumo",
        "tipo_artigo_completo": "Artigo completo",
        "tema_política": "política",
        "tema_saúde": "saúde",
        "tema_economia": "economia",
        "tema_tecnologia": "tecnologia",
        "tema_mundo": "mundo",
        "tema_brasil": "brasil",
        "tema_cultura": "cultura",
        "tema_esportes": "esportes",
        "tema_ciência": "ciência",
        "tema_opinião": "opinião",
        "tema_clima": "clima",
        "weekdays": (
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        ),
        "months": (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ),
    },
    "en": {
        "digest_title": "News Digest",
        "summary": "Summary",
        "relevance_score": "Relevance score",
        "relevance": "Relevance",
        "top_stories": "Top stories by relevance",
        "score": "score",
        "articles": "articles",
        "article_of": "of",
        "read_full": "Read full article online →",
        "contents": "Contents",
        "sections_today": "Your sections for this edition.",
        "edition_overview": "In this edition",
        "also_inside": "Also inside",
        "by_section": "By section",
        "fallback_section_editorial": "{count} stories in {category} today.",
        "fallback_section_lead": "Lead:",
        "fallback_global_headline": "Today's digest",
        "fallback_global_editorial": (
            "Today's digest covers {total} stories across {sections} sections."
        ),
        "tipo_resumo": "Summary",
        "tipo_artigo_completo": "Full article",
        "tema_política": "politics",
        "tema_saúde": "health",
        "tema_economia": "economy",
        "tema_tecnologia": "technology",
        "tema_mundo": "world",
        "tema_brasil": "brazil",
        "tema_cultura": "culture",
        "tema_esportes": "sports",
        "tema_ciência": "science",
        "tema_opinião": "opinion",
        "tema_clima": "climate",
        "weekdays": (
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ),
        "months": (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
    },
    "es": {
        "digest_title": "Resumen de Noticias",
        "summary": "Resumen",
        "relevance_score": "Puntuación de relevancia",
        "relevance": "Relevancia",
        "top_stories": "Noticias principales por relevancia",
        "score": "nota",
        "articles": "artículos",
        "article_of": "de",
        "read_full": "Leer el artículo completo en línea →",
        "contents": "Índice",
        "sections_today": "Tus secciones en esta edición.",
        "edition_overview": "En esta edición",
        "also_inside": "También en esta edición",
        "by_section": "Por sección",
        "fallback_section_editorial": "{count} noticias en {category} hoy.",
        "fallback_section_lead": "Destacado:",
        "fallback_global_headline": "Resumen de hoy",
        "fallback_global_editorial": (
            "Este resumen cubre {total} noticias en {sections} secciones."
        ),
        "tipo_resumo": "Resumen",
        "tipo_artigo_completo": "Artículo completo",
        "tema_política": "política",
        "tema_saúde": "salud",
        "tema_economia": "economía",
        "tema_tecnologia": "tecnología",
        "tema_mundo": "mundo",
        "tema_brasil": "brasil",
        "tema_cultura": "cultura",
        "tema_esportes": "deportes",
        "tema_ciência": "ciencia",
        "tema_opinião": "opinión",
        "tema_clima": "clima",
        "weekdays": (
            "lunes",
            "martes",
            "miércoles",
            "jueves",
            "viernes",
            "sábado",
            "domingo",
        ),
        "months": (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ),
    },
}


def ai_language_code() -> str:
    code = (get_settings().ai_language or "pt-BR").strip()
    return code if code in LANGUAGE_LABELS else code


def ai_language_name() -> str:
    code = ai_language_code()
    return LANGUAGE_LABELS.get(code, code)


def ai_output_language_rule() -> str:
    """Append to AI prompts so generated strings use the configured language."""
    name = ai_language_name()
    code = ai_language_code()
    return (
        f" Language: write ALL user-facing string values (summary, headline, editorial, "
        f"one_liner, story, note, and any rewritten titles) in {name} ({code}). "
        "Keep JSON keys in English."
    )


def summary_language_code() -> str:
    """Configured summary language: a code, or "source" to mirror the article."""
    return (get_settings().summary_language or "").strip()


def ai_summary_language_rule() -> str:
    """Language rule for per-article summaries.

    Unset falls back to the global output rule (upstream behaviour). "source"
    keeps each summary in the language the article was written in, which is what
    a bilingual reader wants from a mixed-language feed list.
    """
    code = summary_language_code()
    if not code:
        return ai_output_language_rule()
    if code == "source":
        return (
            " Language: write each summary in the SAME language as that "
            "article's own title and body — do not translate between "
            "articles. Keep JSON keys in English."
        )
    name = LANGUAGE_LABELS.get(code, code)
    return (
        f" Language: write ALL user-facing string values (summary and any "
        f"rewritten titles) in {name} ({code}). Keep JSON keys in English."
    )


def _labels() -> dict[str, str]:
    code = ai_language_code()
    if code in EPUB_LABELS:
        return EPUB_LABELS[code]
    return EPUB_LABELS["en"]


def _tema_label_key(tema: str) -> str:
    return "tema_" + tema.replace(" ", "_")


def format_tag_line(tipo: str, temas: list[str]) -> str:
    """One-line display: tipo label, then temas joined."""
    tipo_key = "tipo_artigo_completo" if tipo == "artigo-completo" else "tipo_resumo"
    parts = [epub_label(tipo_key)]
    if temas:
        tema_labels = [epub_label(_tema_label_key(t)) for t in temas]
        parts.append(", ".join(tema_labels))
    return " · ".join(parts)


def epub_label(key: str, **kwargs: str | int) -> str:
    text = _labels().get(key, EPUB_LABELS["en"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text


def format_digest_date(when: datetime) -> str:
    labels = _labels()
    weekday = labels["weekdays"][when.weekday()]
    month = labels["months"][when.month - 1]
    code = ai_language_code()
    if code == "pt-BR":
        return f"{weekday}, {when.day} de {month} de {when.year}"
    return when.strftime("%A, %B %d, %Y")


def format_digest_timestamp(when: datetime) -> str:
    """Title-safe date/time for EPUB filenames and headers."""
    labels = _labels()
    month = labels["months"][when.month - 1]
    code = ai_language_code()
    if code == "pt-BR":
        return f"{when.day} {month} {when.year} {when.strftime('%H%M')}"
    return when.strftime("%B %d %Y %H%M")
