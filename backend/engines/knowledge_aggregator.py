"""
engines/knowledge_aggregator.py
Stage 2.5: Knowledge Aggregator

Runs AFTER the 5 parallel engines, BEFORE Synthesis.
Aggregates everything the system already knows about this story:
  - Previous analysis versions and score trends
  - Historical defects (open, fixed, reopened)
  - Knowledge base entries linked or relevant
  - Story family (parent/children)
  - Recurring findings across versions

This context feeds the Synthesis Engine so it can correlate
fresh findings with institutional memory.
"""

from typing import Optional
from models.schemas import NormalizedRequirement
from utils.id_detector import detect_story_id


class KnowledgeAggregatorResult:
    def __init__(self):
        self.story_id:          Optional[str] = None
        self.has_history:       bool          = False
        self.version_trend:     str           = ""   # improving | degrading | stable | first
        self.previous_versions: list          = []
        self.defects_summary:   dict          = {}
        self.kb_entries:        list          = []
        self.family:            dict          = {}
        self.recurring_risks:   list          = []
        self.context_block:     str           = ""   # formatted for Synthesis prompt

    def to_dict(self) -> dict:
        return {
            "story_id":          self.story_id,
            "has_history":       self.has_history,
            "version_trend":     self.version_trend,
            "previous_versions": self.previous_versions,
            "defects_summary":   self.defects_summary,
            "kb_entries":        self.kb_entries,
            "family":            self.family,
            "recurring_risks":   self.recurring_risks,
            "context_block":     self.context_block,
        }


async def run(
    requirement:    str,
    normalized:     NormalizedRequirement,
    project_id:     Optional[str] = None,
) -> KnowledgeAggregatorResult:
    """
    Aggregate all institutional knowledge for this story.
    Never calls AI — pure data aggregation from the database.
    """
    result = KnowledgeAggregatorResult()

    story_id = detect_story_id(requirement)
    result.story_id = story_id

    if not story_id:
        result.version_trend = "first"
        result.context_block = _build_context_block(result, normalized)
        return result

    # ── Load from repositories ────────────────────────────────────────────────
    try:
        from repositories.analysis    import AnalysisRepository
        from repositories.defects     import DefectsRepository
        from repositories.story_links import StoryLinksRepository
        from repositories.knowledge   import KnowledgeRepository

        analysis_repo  = AnalysisRepository()
        defects_repo   = DefectsRepository()
        links_repo     = StoryLinksRepository()
        knowledge_repo = KnowledgeRepository()

        # Previous versions
        versions = analysis_repo.list_by_story_id(story_id)
        result.previous_versions = versions
        result.has_history = len(versions) > 0

        # Version trend
        result.version_trend = _compute_trend(versions)

        # Defects
        result.defects_summary = defects_repo.get_summary(story_id)

        # Family
        result.family = links_repo.get_family(story_id)

        # KB entries — direct links + keyword search
        kb_context = links_repo.get_story_context(story_id)
        direct   = kb_context.get("direct_knowledge", [])
        inherited = kb_context.get("inherited_knowledge", [])
        keyword_hits = knowledge_repo.get_context_for_analysis(
            keywords=normalized.keywords,
            project_id=project_id,
        )
        # Merge, deduplicate by id
        seen = set()
        for e in direct + inherited + keyword_hits:
            eid = e.get("id") or e.get("knowledge_id")
            if eid and eid not in seen:
                seen.add(eid)
                result.kb_entries.append(e)

        # Recurring risks — findings that appeared in multiple versions
        result.recurring_risks = _find_recurring(versions)

    except Exception:
        # Never fail the pipeline because of aggregation errors
        result.version_trend = "first" if not result.has_history else "stable"

    result.context_block = _build_context_block(result, normalized)
    return result


def _compute_trend(versions: list) -> str:
    """Compute score trend across versions."""
    if not versions:
        return "first"
    if len(versions) == 1:
        return "stable"

    scores = [v.get("overall_score") for v in versions if v.get("overall_score") is not None]
    if len(scores) < 2:
        return "stable"

    # Compare last 2 versions (newest first)
    latest = scores[0]
    prev   = scores[1]
    delta  = latest - prev

    if delta >= 5:  return "improving"
    if delta <= -5: return "degrading"
    return "stable"


def _find_recurring(versions: list) -> list:
    """
    Identify risk patterns that appeared across multiple versions.
    Uses risk_level as a simple proxy — can be enhanced later.
    """
    if len(versions) < 2:
        return []

    recurring = []
    critical_count = sum(1 for v in versions if v.get("risk_level") in ("critical", "high"))
    if critical_count >= 2:
        recurring.append(
            f"Risco alto/crítico persistente em {critical_count} de {len(versions)} versões analisadas"
        )

    return recurring


def _build_context_block(result: KnowledgeAggregatorResult, normalized: NormalizedRequirement) -> str:
    """Format aggregated knowledge as context string for Synthesis."""
    lines = []

    # ── Version history ───────────────────────────────────────────────────────
    if result.has_history:
        versions = result.previous_versions
        latest   = versions[0] if versions else {}
        trend_emoji = {"improving":"📈","degrading":"📉","stable":"➡","first":"🆕"}.get(result.version_trend,"")
        lines.append(f"HISTÓRICO DA HISTÓRIA {result.story_id}:")
        lines.append(
            f"  {len(versions)} versão(ões) analisada(s) {trend_emoji} "
            f"Tendência: {result.version_trend}"
        )
        if latest:
            lines.append(
                f"  Última análise: score {latest.get('overall_score','—')} · "
                f"risk {latest.get('risk_level','—')} · "
                f"v{latest.get('version','—')}"
            )
        if result.recurring_risks:
            lines.append("  Padrões recorrentes:")
            for r in result.recurring_risks:
                lines.append(f"    → {r}")

    # ── Defects ───────────────────────────────────────────────────────────────
    d = result.defects_summary
    if d and d.get("total", 0) > 0:
        lines.append(f"\nDEFEITOS DA HISTÓRIA:")
        lines.append(
            f"  Total: {d['total']} · Abertos: {d.get('open',0)} · "
            f"Critical: {d.get('critical',0)} · High: {d.get('high',0)}"
        )
        by_type = d.get("by_type", {})
        if by_type:
            lines.append(
                f"  Por tipo: QA={by_type.get('qa',0)} · "
                f"Produção={by_type.get('production',0)} · "
                f"Regressão={by_type.get('regression',0)}"
            )
        for defect in d.get("defects", [])[:3]:
            status = defect.get("status","")
            jira   = f" [{defect['jira_id']}]" if defect.get("jira_id") else ""
            lines.append(
                f"  [{defect.get('severity','').upper()} · {status}{jira}] "
                f"{defect.get('title','')}"
            )

    # ── Family ────────────────────────────────────────────────────────────────
    fam = result.family
    if fam:
        parent = fam.get("parent_story")
        children = fam.get("children", [])
        if parent:
            lines.append(f"\nEsta história é uma MELHORIA de {parent.get('parent_id','?')}")
            lines.append("  Considere o contexto e defeitos da história pai na análise.")
        if children:
            child_ids = [c.get("child_id","") for c in children]
            lines.append(f"\nMelhorias vinculadas: {', '.join(child_ids)}")

    # ── KB entries ────────────────────────────────────────────────────────────
    if result.kb_entries:
        lines.append(f"\nCONHECIMENTO CORPORATIVO RELEVANTE ({len(result.kb_entries)} entradas):")
        cat_label = {
            "padrao":"Padrão","bug":"Bug Histórico","integ":"Integração",
            "gloss":"Glossário","comp":"Compliance","risco":"Risco","heur":"Heurística"
        }
        for e in result.kb_entries[:6]:
            cat  = cat_label.get(e.get("category",""), e.get("category",""))
            sev  = f" · {e.get('severity','')}" if e.get("severity") else ""
            lines.append(f"  [{cat}{sev}] {e.get('title','')}")
            desc = e.get("description","")[:200]
            if desc:
                lines.append(f"    → {desc}")

    return "\n".join(lines) if lines else ""
