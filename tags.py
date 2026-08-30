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

_SUBSCRIBE_RE = re.compile(
    r"assine|subscribe|paywall|continue\s+reading|continue\s+lendo|"
    r"leia\s+mais|cadastre-se",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _body_matches_snippet(body: str, art: dict) -> bool:
    """True when body is nearly the same as the title/RSS snippet."""
    title = (art.get("title") or "").strip()
    if not body or not title:
        return False

    body_norm = _normalize_text(body)
    title_norm = _normalize_text(title)
    if not body_norm or not title_norm:
        return False

    if body_norm == title_norm:
        return True

    if len(body) < 80 and body_norm in title_norm:
        return True

    if len(title) < 80 and title_norm in body_norm:
        extra = len(body_norm) - len(title_norm)
        if extra <= 30:
            return True

    return SequenceMatcher(None, body_norm, title_norm).ratio() >= 0.92


def infer_tipo(art: dict) -> str:
    """Heuristic completeness: resumo vs artigo-completo."""
    body = (art.get("content") or "").strip()
    min_chars = get_settings().min_body_chars

    if len(body) < min_chars:
        return "resumo"

    if _body_matches_snippet(body, art):
        return "resumo"

    if _SUBSCRIBE_RE.search(body):
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
            temas = [t for t in raw_temas if t in TEMAS]

    art["tipo"] = tipo
    art["temas"] = temas
    return art
