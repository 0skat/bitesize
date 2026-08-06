"""Language settings for AI-generated text and EPUB labels."""

from __future__ import annotations

from datetime import datetime

from config import get_settings

LANGUAGE_LABELS: dict[str, str] = {
    "pt-BR": "Brazilian Portuguese",
    "en": "English",
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


def _labels() -> dict[str, str]:
    code = ai_language_code()
    if code in EPUB_LABELS:
        return EPUB_LABELS[code]
    return EPUB_LABELS["en"]


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
