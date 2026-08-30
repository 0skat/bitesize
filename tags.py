"""Article tipo (completeness) and temas (pt-BR topics)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from config import get_settings

TIPOS = frozenset({"resumo", "artigo-completo"})

TEMAS = frozenset({
    "política",
    "saúde",
    "economia",
    "tecnologia",
    "mundo",
    "brasil",
    "cultura",
    "esportes",
    "ciência",
    "opinião",
    "clima",
})

# Paywall/snippet heuristics apply only to bodies no longer than this multiple of min_body_chars.
TIPO_SHORT_BODY_MULTIPLIER = 2

_SUBSCRIBE_RE = re.compile(
    r"\bassine\b|\bsubscribe\b|\bpaywall\b|"
    r"\bcontinue\s+reading\b|\bcontinue\s+lendo\b|\bcadastre-se\b",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _snippet_echo_max_chars() -> int:
    return get_settings().min_body_chars * TIPO_SHORT_BODY_MULTIPLIER


def _texts_nearly_equal(a: str, b: str) -> bool:
    """True when two strings are the same teaser (exact, substring, or ≥92% similar)."""
    a_norm = _normalize_text(a)
    b_norm = _normalize_text(b)
    if not a_norm or not b_norm:
        return False

    if a_norm == b_norm:
        return True

    if len(a) < 80 and a_norm in b_norm:
        return True

    if len(b) < 80 and b_norm in a_norm:
        extra = len(a_norm) - len(b_norm) if len(a_norm) >= len(b_norm) else len(b_norm) - len(a_norm)
        if extra <= 30:
            return True

    return SequenceMatcher(None, a_norm, b_norm).ratio() >= 0.92


def _body_matches_snippet(body: str, art: dict) -> bool:
    """True when a short body echoes the title or the stored RSS description.

    RSS text lives in ``rss_snippet`` (set at feed fetch). Before full-text
    replace, ``content`` is the same string; after replace, only ``rss_snippet``
    keeps the original feed description for comparison.
    """
    if len(body) > _snippet_echo_max_chars():
        return False

    title = (art.get("title") or "").strip()
    rss = (art.get("rss_snippet") or "").strip()

    if title and _texts_nearly_equal(body, title):
        return True

    if rss and _texts_nearly_equal(body, rss):
        return True

    return False


def infer_tipo(art: dict) -> str:
    """Heuristic completeness: resumo vs artigo-completo."""
    body = (art.get("content") or "").strip()
    min_chars = get_settings().min_body_chars

    if len(body) < min_chars:
        return "resumo"

    if _body_matches_snippet(body, art):
        return "resumo"

    if len(body) <= _snippet_echo_max_chars() and _SUBSCRIBE_RE.search(body):
        return "resumo"

    return "artigo-completo"


def normalize_tags(art: dict, ai_item: dict | None = None) -> dict:
    """Set tipo and temas on art; AI values override heuristics when valid."""
    heuristic_tipo = infer_tipo(art)
    tipo = heuristic_tipo

    if ai_item and "tipo" in ai_item:
        raw_tipo = ai_item.get("tipo")
        if raw_tipo in TIPOS:
            tipo = raw_tipo

    temas: list[str] = []
    if ai_item and "temas" in ai_item:
        raw_temas = ai_item.get("temas")
        if isinstance(raw_temas, list):
            seen: set[str] = set()
            for t in raw_temas:
                if t in TEMAS and t not in seen:
                    seen.add(t)
                    temas.append(t)

    art["tipo"] = tipo
    art["temas"] = temas
    return art
