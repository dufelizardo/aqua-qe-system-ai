"""
utils/knowledge_context.py
Builds corporate knowledge context for the Normalizer.

Retrieves relevant entries from the knowledge base based on
keywords extracted from the requirement text, and formats
them as a context block to inject into the Normalizer prompt.
"""

from typing import Optional
from repositories.knowledge   import KnowledgeRepository
from repositories.story_links import StoryLinksRepository
from repositories.defects     import DefectsRepository
from utils.id_detector        import detect_story_id

knowledge_repo    = KnowledgeRepository()
story_links_repo  = StoryLinksRepository()
defects_repo      = DefectsRepository()

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
    
    Two sources combined:
    1. Story-specific links (directly linked to this story ID)
    2. Keyword-based search (relevant entries from the full KB)
    
    Returns empty string if nothing relevant found.
    """
    lines = []

    # ── Source 1: Story-specific knowledge ───────────────────────────────────
    story_id = detect_story_id(requirement)
    if story_id:
        ctx = story_links_repo.get_story_context(story_id)
        direct    = ctx.get("direct_knowledge", [])
        inherited = ctx.get("inherited_knowledge", [])
        parent    = ctx.get("parent_story")

        if direct or inherited:
            lines.append(f"CONHECIMENTO VINCULADO À HISTÓRIA {story_id}:")

            if parent:
                lines.append(
                    f"(Melhoria de {parent['parent_id']} — "
                    f"contexto herdado da história principal)"
                )

            for e in direct:
                _append_entry(lines, e, source="direto")

            if inherited:
                lines.append(f"\nCONHECIMENTO HERDADO DE {parent['parent_id']}:")
                for e in inherited:
                    _append_entry(lines, e, source="herdado")

    # ── Source 2: Keyword-based search ───────────────────────────────────────
    keywords = _extract_keywords(requirement)
    if keywords:
        entries = knowledge_repo.get_context_for_analysis(
            keywords=keywords,
            project_id=project_id,
        )
        if entries:
            if lines:
                lines.append("\nCONHECIMENTO CORPORATIVO RELEVANTE (por palavras-chave):")
            else:
                lines.append("CONTEXTO CORPORATIVO (base de conhecimento da empresa):")

            for e in entries[:6]:
                _append_entry(lines, e)

    # ── Source 3: Historical defects for this story ───────────────────────────
    if story_id:
        defects_ctx = defects_repo.format_for_pipeline(story_id)
        if defects_ctx:
            lines.append(defects_ctx)

        # Also check parent story defects (inherited)
        parent = story_links_repo.get_parent(story_id)
        if parent:
            parent_defects = defects_repo.format_for_pipeline(parent["parent_id"])
            if parent_defects:
                lines.append(
                    f"\nDEFEITOS HERDADOS DA HISTÓRIA PAI {parent['parent_id']}:"
                )
                lines.append(parent_defects)

    if not lines:
        return ""

    lines.append(
        "\nUse este contexto para enriquecer a análise. "
        "Considere bugs históricos, padrões e riscos conhecidos."
    )
    return "\n".join(lines)


def _append_entry(lines: list, e: dict, source: str = "") -> None:
    """Format a knowledge entry into the context block."""
    cat_label = CATEGORY_LABEL.get(e.get("category", ""), e.get("category", ""))
    title     = e.get("title", "")
    desc      = e.get("description", "")[:280]
    sev       = e.get("severity", "")
    sev_str   = f" · Severidade: {sev}" if sev else ""
    note      = e.get("note", "")

    lines.append(f"\n[{cat_label}{sev_str}] {title}")
    lines.append(f"  → {desc}")

    if note:
        lines.append(f"  → Nota: {note}")

    mitigation = e.get("mitigation", "")
    if mitigation:
        lines.append(f"  → Mitigação: {mitigation[:200]}")


def _extract_keywords(text: str) -> list[str]:
    """
    Extract meaningful keywords from requirement text.
    Simple approach: split, clean, filter stopwords.
    """
    import re

    stopwords = {
        "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
        "um", "uma", "o", "a", "os", "as", "e", "ou", "que", "se",
        "para", "com", "por", "ao", "à", "the", "a", "an", "and", "or",
        "to", "of", "in", "on", "at", "for", "with", "is", "are", "be",
        "deve", "deve-se", "deverá", "deve-se", "deve", "dever", "sendo",
        "como", "quando", "onde", "qual", "quais", "este", "esta", "isso",
        "não", "sem", "após", "antes", "durante", "sobre",
    }

    # Extract words (3+ chars)
    words = re.findall(r'\b[A-Za-zÀ-ÿ]{3,}\b', text)
    keywords = [
        w for w in words
        if w.lower() not in stopwords and not w.isdigit()
    ]

    # Also extract IDs and technical terms (BSAG-1724, ISIN, etc.)
    ids = re.findall(r'\b[A-Z]{2,}-\d+\b|\b[A-Z]{3,}\b', text)
    keywords.extend(ids)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for k in keywords:
        if k.lower() not in seen:
            seen.add(k.lower())
            unique.append(k)

    return unique[:20]  # max 20 keywords for search
