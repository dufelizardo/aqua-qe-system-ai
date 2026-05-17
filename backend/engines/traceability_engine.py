"""
engines/traceability.py
Traceability Engine

Runs after the parallel engines and Knowledge Aggregator, before Synthesis.
Generates a RTM (Requirements Traceability Matrix) by:

1. Inferring links from findings (Ambiguity, Risk, Rules, Gap, Coverage)
2. Loading existing links from the database (if story has previous analyses)
3. Computing coverage per requirement
4. Producing an executive summary

No AI call — pure correlation of structured data already produced by other engines.
"""

from typing import Optional
from models.schemas import (
    NormalizedRequirement,
    AmbiguityResult, RiskResult, RulesResult, GapResult, CoverageResult,
    TraceabilityResult, TraceabilityItem, EngineStatus,
)
from utils.id_detector import detect_story_id


async def run(
    normalized:  NormalizedRequirement,
    ambiguity:   Optional[AmbiguityResult],
    risk:        Optional[RiskResult],
    rules:       Optional[RulesResult],
    gap:         Optional[GapResult],
    coverage:    Optional[CoverageResult],
    requirement: str = "",
    project_id:  Optional[str] = None,
) -> TraceabilityResult:
    """
    Build RTM from all available engine outputs.
    """
    result = TraceabilityResult()

    # ── Extract requirement IDs from normalized text ──────────────────────────
    req_ids = _extract_req_ids(normalized)

    if not req_ids:
        # No structured req IDs — create one synthetic entry
        req_ids = [{"id": "REQ-001", "title": normalized.intent or normalized.normalized[:80]}]

    # ── Build RTM items ───────────────────────────────────────────────────────
    items = []
    for req in req_ids:
        item = TraceabilityItem(
            req_id=req["id"],
            req_title=req["title"],
        )

        # Rules linked to this requirement
        if rules:
            item.rules = [
                f.title for f in rules.findings
                if _is_relevant(f, req["id"], req["title"])
            ][:5]
            # Also include extracted rules_found
            if rules.rules_found and not item.rules:
                item.rules = rules.rules_found[:3]

        # Criteria — derived from ambiguity findings (what needs to be clarified = implicit criteria)
        if ambiguity:
            item.criteria = [
                f"CA: {f.suggestion[:80]}" for f in ambiguity.findings
                if f.suggestion and _is_relevant(f, req["id"], req["title"])
            ][:4]

        # Risks linked to this requirement
        if risk:
            item.risks = [
                f.title for f in risk.findings
                if _is_relevant(f, req["id"], req["title"])
            ][:5]

        # Gaps — scenarios that should exist but don't
        if gap:
            item.gaps = [
                f.title for f in gap.findings
                if _is_relevant(f, req["id"], req["title"])
            ][:4]
            # Add missing scenarios as scenario placeholders
            item.scenarios = [
                f"CT: {m[:80]}" for m in (gap.missing or [])[:3]
            ]

        # Coverage from coverage engine
        if coverage:
            covered   = coverage.covered or []
            uncovered = coverage.uncovered or []
            if covered and not uncovered:
                item.coverage = "full"
                item.coverage_pct = 100
            elif covered and uncovered:
                total = len(covered) + len(uncovered)
                item.coverage = "partial"
                item.coverage_pct = round(len(covered) / total * 100) if total else 0
            else:
                item.coverage = "none"
                item.coverage_pct = 0

        items.append(item)

    # ── Load existing links from DB ───────────────────────────────────────────
    story_id = detect_story_id(requirement)
    if story_id:
        try:
            from repositories.story_links import StoryLinksRepository
            links_repo = StoryLinksRepository()
            kb_ctx = links_repo.get_story_context(story_id)
            kb_entries = kb_ctx.get("direct_knowledge", [])

            # Enrich items with KB knowledge entries
            for item in items:
                for entry in kb_entries:
                    cat = entry.get("category", "")
                    title = entry.get("title", "")
                    if cat == "risco" and title not in item.risks:
                        item.risks.append(f"[KB] {title}"[:80])
                    elif cat == "padrao" and title not in item.criteria:
                        item.criteria.append(f"[KB] {title}"[:80])
        except Exception:
            pass

    result.items = items

    # ── Compute overall coverage ──────────────────────────────────────────────
    if items:
        avg = sum(i.coverage_pct for i in items) / len(items)
        result.overall_coverage = round(avg)
        result.uncovered = [
            i.req_id for i in items if i.coverage == "none"
        ]

    # ── Executive summary ─────────────────────────────────────────────────────
    total      = len(items)
    full_cov   = sum(1 for i in items if i.coverage == "full")
    partial    = sum(1 for i in items if i.coverage == "partial")
    none_cov   = sum(1 for i in items if i.coverage == "none")
    total_risks = sum(len(i.risks) for i in items)
    total_gaps  = sum(len(i.gaps)  for i in items)

    result.summary = (
        f"{total} requisito(s) mapeado(s). "
        f"Cobertura: {full_cov} completo(s), {partial} parcial(is), {none_cov} descoberto(s). "
        f"{total_risks} risco(s) e {total_gaps} gap(s) identificado(s)."
    )

    if result.overall_coverage >= 75:
        result.verdict = "Rastreabilidade adequada — cobertura acima de 75%"
    elif result.overall_coverage >= 50:
        result.verdict = "Rastreabilidade parcial — gaps relevantes a endereçar"
    else:
        result.verdict = "Rastreabilidade insuficiente — requisitos com baixa cobertura"

    result.status = EngineStatus.DONE
    return result


def _extract_req_ids(normalized: NormalizedRequirement) -> list[dict]:
    """
    Extract structured requirement IDs and titles from normalized text.
    Looks for patterns like REQ-01, RN-01, CA-01, etc.
    """
    import re
    text = normalized.original or normalized.normalized or ""
    items = []
    seen  = set()

    # Pattern: REQ-01: title, RN-01. title, CA-01 - title
    pattern = re.compile(
        r'\b((?:REQ|RN|CA|US|HU|RF|RNF)-?\d+)[:\.\-\s]+([^\n]{10,80})',
        re.IGNORECASE
    )
    for m in pattern.finditer(text):
        req_id    = m.group(1).upper()
        req_title = m.group(2).strip().rstrip('.')
        if req_id not in seen:
            seen.add(req_id)
            items.append({"id": req_id, "title": req_title[:100]})

    # Fallback: use actions as implicit requirements
    if not items and normalized.actions:
        for i, action in enumerate(normalized.actions[:5], 1):
            items.append({"id": f"REQ-{i:02d}", "title": action})

    return items


def _is_relevant(finding, req_id: str, req_title: str) -> bool:
    """
    Check if a finding is relevant to a specific requirement.
    Simple heuristic: check refs or title/description overlap.
    """
    # Check refs
    refs = [r.upper() for r in (finding.refs or [])]
    if req_id.upper() in refs:
        return True

    # Check title overlap (at least 2 words in common)
    req_words = set(req_title.lower().split())
    find_words = set((finding.title + " " + finding.description).lower().split())
    common = req_words & find_words - {"a","o","e","de","da","do","para","com","que","em","na","no","um","uma"}
    return len(common) >= 2
