"""
utils/knowledge_context.py
Knowledge Layer 3c - Context Builder

Uses semantic search (TF-IDF) instead of keyword matching.
Provides engine-specific context for richer, more accurate analysis.
"""

from typing import Optional
from utils.id_detector import detect_story_id


CATEGORY_LABEL = {
    "padrao": "Padrão Corporativo",
    "bug":    "Bug Histórico",
    "integ":  "Integração Conhecida",
    "gloss":  "Glossário",
    "comp":   "Compliance / Regulatório",
    "risco":  "Risco Conhecido",
    "heur":   "Heurística QA",
}


def build_context(requirement: str, project_id: Optional[str] = None) -> str:
    """
    Build corporate knowledge context for the Normalizer.
    Uses semantic search for better relevance.
    """
    lines = []

    # ── Source 1: Story-specific knowledge ───────────────────────────────────
    story_id = detect_story_id(requirement)
    if story_id:
        try:
            from repositories.story_links import StoryLinksRepository
            from repositories.defects     import DefectsRepository
            links_repo   = StoryLinksRepository()
            defects_repo = DefectsRepository()

            ctx      = links_repo.get_story_context(story_id)
            direct   = ctx.get("direct_knowledge", [])
            inherited= ctx.get("inherited_knowledge", [])
            parent   = ctx.get("parent_story")

            if direct or inherited:
                lines.append(f"CONHECIMENTO VINCULADO À HISTÓRIA {story_id}:")
                if parent:
                    lines.append(f"(Melhoria de {parent['parent_id']} — contexto herdado)")
                for e in direct:
                    _append_entry(lines, e, source="direto")
                if inherited:
                    lines.append(f"\nCONHECIMENTO HERDADO DE {parent['parent_id']}:")
                    for e in inherited:
                        _append_entry(lines, e, source="herdado")

            # Defects
            defects_ctx = defects_repo.format_for_pipeline(story_id)
            if defects_ctx:
                lines.append(defects_ctx)

            # Parent defects
            if parent:
                parent_defects = defects_repo.format_for_pipeline(parent["parent_id"])
                if parent_defects:
                    lines.append(f"\nDEFEITOS HERDADOS DE {parent['parent_id']}:")
                    lines.append(parent_defects)

        except Exception:
            pass

    # ── Source 2: Semantic search ─────────────────────────────────────────────
    try:
        from utils.semantic_search import search_kb, format_for_prompt
        semantic_results = search_kb(
            query=requirement,
            engine="normalizer",
            project_id=project_id,
            top_k=8,
        )
        if semantic_results:
            semantic_ctx = format_for_prompt(semantic_results, engine="normalizer")
            if semantic_ctx:
                lines.append("\n" + semantic_ctx)
    except Exception:
        # Fallback to keyword search if semantic fails
        try:
            from repositories.knowledge import KnowledgeRepository
            kb = KnowledgeRepository()
            keywords = _extract_keywords(requirement)
            entries = kb.get_context_for_analysis(keywords=keywords, project_id=project_id)
            if entries:
                lines.append("\nCONHECIMENTO CORPORATIVO (por palavras-chave):")
                for e in entries[:6]:
                    _append_entry(lines, e)
        except Exception:
            pass

    if not lines:
        return ""

    lines.append(
        "\nUse este contexto para enriquecer a análise. "
        "Priorize entradas com maior confiança e recorrência."
    )
    return "\n".join(lines)


def build_engine_context(requirement: str, engine: str,
                         project_id: Optional[str] = None) -> str:
    """
    Build engine-specific context using semantic search.
    Each engine receives only relevant KB categories.
    """
    try:
        from utils.semantic_search import search_kb, format_for_prompt
        results = search_kb(
            query=requirement,
            engine=engine,
            project_id=project_id,
            top_k=5,
        )
        if results:
            return format_for_prompt(results, engine=engine)
    except Exception:
        pass
    return ""


def _append_entry(lines: list, e: dict, source: str = "") -> None:
    cat_label  = CATEGORY_LABEL.get(e.get("category", ""), e.get("category", ""))
    title      = e.get("title", "")
    desc       = e.get("description", "")[:280]
    sev        = e.get("severity", "")
    sev_str    = f" · Severidade: {sev}" if sev else ""
    note       = e.get("note", "")
    confidence = e.get("_confidence", "")
    conf_str   = f" · Confiança: {confidence:.0%}" if isinstance(confidence, float) else ""

    lines.append(f"\n[{cat_label}{sev_str}{conf_str}] {title}")
    lines.append(f"  → {desc}")
    if note:
        lines.append(f"  → Nota: {note}")
    mit = e.get("mitigation", "")
    if mit:
        lines.append(f"  → Mitigação: {mit[:200]}")


def _extract_keywords(text: str) -> list[str]:
    import re
    stopwords = {
        "de","da","do","das","dos","em","no","na","nos","nas","um","uma",
        "o","a","os","as","e","ou","que","se","para","com","por","ao","à",
        "deve","sendo","como","quando","onde","qual","este","esta","não","sem",
    }
    words  = re.findall(r'\b[A-Za-zÀ-ÿ]{3,}\b', text)
    kws    = [w for w in words if w.lower() not in stopwords and not w.isdigit()]
    ids    = re.findall(r'\b[A-Z]{2,}-\d+\b|\b[A-Z]{3,}\b', text)
    kws.extend(ids)
    seen, unique = set(), []
    for k in kws:
        if k.lower() not in seen:
            seen.add(k.lower())
            unique.append(k)
    return unique[:20]
