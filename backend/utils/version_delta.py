"""
utils/version_delta.py
Knowledge Layer 3c — Version Delta Analyzer

Detects what changed between two versions of a requirement:
  - RNs added / removed / modified
  - CAs added / removed / modified
  - New keywords / actors / constraints
  - Complexity change

Used by:
  - Traceability Engine v2 (impact analysis)
  - Knowledge Layer (what to re-enrich)
  - Frontend (show diff between versions)
"""

import re
from typing import Optional
from dataclasses import dataclass, field


# ── Structures ────────────────────────────────────────────────────────────────

@dataclass
class DeltaItem:
    id:          str        # RN-01, CA-03, etc.
    type:        str        # rn | ca | rf | actor | keyword
    action:      str        # added | removed | modified
    old_text:    str = ""
    new_text:    str = ""
    impact:      str = ""   # high | medium | low
    description: str = ""


@dataclass
class VersionDelta:
    story_id:        Optional[str] = None
    v_from:          int = 0
    v_to:            int = 0
    has_changes:     bool = False
    items:           list[DeltaItem] = field(default_factory=list)
    added_rns:       list[str] = field(default_factory=list)
    removed_rns:     list[str] = field(default_factory=list)
    modified_rns:    list[str] = field(default_factory=list)
    added_cas:       list[str] = field(default_factory=list)
    removed_cas:     list[str] = field(default_factory=list)
    modified_cas:    list[str] = field(default_factory=list)
    new_keywords:    list[str] = field(default_factory=list)
    removed_keywords:list[str] = field(default_factory=list)
    impact_level:    str = "none"   # none | low | medium | high | critical
    summary:         str = ""
    affected:        list[str] = field(default_factory=list)  # IDs affected by changes

    def to_dict(self) -> dict:
        return {
            "story_id":         self.story_id,
            "v_from":           self.v_from,
            "v_to":             self.v_to,
            "has_changes":      self.has_changes,
            "added_rns":        self.added_rns,
            "removed_rns":      self.removed_rns,
            "modified_rns":     self.modified_rns,
            "added_cas":        self.added_cas,
            "removed_cas":      self.removed_cas,
            "modified_cas":     self.modified_cas,
            "new_keywords":     self.new_keywords,
            "removed_keywords": self.removed_keywords,
            "impact_level":     self.impact_level,
            "summary":          self.summary,
            "affected":         self.affected,
            "items": [
                {
                    "id":          i.id,
                    "type":        i.type,
                    "action":      i.action,
                    "old_text":    i.old_text,
                    "new_text":    i.new_text,
                    "impact":      i.impact,
                    "description": i.description,
                }
                for i in self.items
            ],
        }


# ── Extraction ────────────────────────────────────────────────────────────────

def _extract_sections(text: str) -> dict[str, str]:
    """
    Extract RN and CA sections from requirement text.
    Returns dict: {"RN-01": "text...", "CA-01": "text...", ...}
    """
    sections = {}

    # Pattern: RN-01, RN-01.1, CA-01, etc.
    pattern = re.compile(
        r'\b((?:RN|CA|RF|RNF)-\d+(?:\.\d+)?)\b[.\s\u2013\u2014\-]*(.*?)(?=\n\s*(?:RN|CA|RF|RNF)-\d+|\Z)',
        re.DOTALL | re.IGNORECASE
    )

    for m in pattern.finditer(text):
        item_id   = m.group(1).upper().strip()
        item_text = m.group(2).strip()
        # Clean up whitespace
        item_text = re.sub(r'\s+', ' ', item_text)[:500]
        if item_text:
            sections[item_id] = item_text

    return sections


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful domain keywords."""
    stopwords = {
        'de','da','do','das','dos','em','no','na','o','a','os','as','e','ou',
        'que','se','para','com','por','ao','deve','sendo','como','quando',
        'onde','qual','este','esta','não','sem','após','antes','durante',
        'deve','deverá','será','system','user','usuário','sistema',
    }
    words = re.findall(r'\b[A-Za-zÀ-ÿ]{4,}\b', text.lower())
    return set(w for w in words if w not in stopwords)


def _text_similarity(t1: str, t2: str) -> float:
    """Simple word overlap similarity."""
    w1 = set(t1.lower().split())
    w2 = set(t2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def _assess_impact(item_id: str, action: str, text: str) -> str:
    """Assess impact level of a change."""
    high_keywords = {
        'segurança','security','autenticação','autorizacao','permissão',
        'auditoria','lgpd','compliance','regulat','bloqueio','block',
        'crítico','critical','financeiro','financial','isin','pagamento',
    }
    medium_keywords = {
        'performance','timeout','cache','paginação','validação','erro',
        'notificação','log','session','sessão',
    }

    text_lower = text.lower()

    if any(kw in text_lower for kw in high_keywords):
        return "high"
    if any(kw in text_lower for kw in medium_keywords):
        return "medium"
    if action == "removed":
        return "high"  # Removing a rule is always impactful
    return "low"


# ── Main delta function ───────────────────────────────────────────────────────

def compute_delta(
    old_text: str,
    new_text: str,
    story_id: Optional[str] = None,
    v_from: int = 1,
    v_to: int = 2,
) -> VersionDelta:
    """
    Compute the delta between two versions of a requirement text.
    Returns a VersionDelta with all changes detected.
    """
    delta = VersionDelta(story_id=story_id, v_from=v_from, v_to=v_to)

    if old_text.strip() == new_text.strip():
        delta.summary = "Texto idêntico — nenhuma mudança detectada."
        return delta

    delta.has_changes = True

    # Extract sections from both versions
    old_sections = _extract_sections(old_text)
    new_sections  = _extract_sections(new_text)

    old_rns = {k: v for k, v in old_sections.items() if k.startswith("RN")}
    old_cas = {k: v for k, v in old_sections.items() if k.startswith("CA")}
    new_rns  = {k: v for k, v in new_sections.items()  if k.startswith("RN")}
    new_cas  = {k: v for k, v in new_sections.items()  if k.startswith("CA")}

    # ── RN changes ────────────────────────────────────────────────────────────
    for rn_id in set(list(old_rns.keys()) + list(new_rns.keys())):
        if rn_id in new_rns and rn_id not in old_rns:
            # Added
            delta.added_rns.append(rn_id)
            impact = _assess_impact(rn_id, "added", new_rns[rn_id])
            delta.items.append(DeltaItem(
                id=rn_id, type="rn", action="added",
                new_text=new_rns[rn_id],
                impact=impact,
                description=f"{rn_id} adicionada: {new_rns[rn_id][:100]}",
            ))
        elif rn_id in old_rns and rn_id not in new_rns:
            # Removed
            delta.removed_rns.append(rn_id)
            delta.items.append(DeltaItem(
                id=rn_id, type="rn", action="removed",
                old_text=old_rns[rn_id],
                impact="high",
                description=f"{rn_id} removida: {old_rns[rn_id][:100]}",
            ))
        else:
            # Check if modified
            sim = _text_similarity(old_rns[rn_id], new_rns[rn_id])
            if sim < 0.85:
                delta.modified_rns.append(rn_id)
                impact = _assess_impact(rn_id, "modified", new_rns[rn_id])
                delta.items.append(DeltaItem(
                    id=rn_id, type="rn", action="modified",
                    old_text=old_rns[rn_id],
                    new_text=new_rns[rn_id],
                    impact=impact,
                    description=f"{rn_id} modificada (similaridade: {sim:.0%})",
                ))

    # ── CA changes ────────────────────────────────────────────────────────────
    for ca_id in set(list(old_cas.keys()) + list(new_cas.keys())):
        if ca_id in new_cas and ca_id not in old_cas:
            delta.added_cas.append(ca_id)
            impact = _assess_impact(ca_id, "added", new_cas[ca_id])
            delta.items.append(DeltaItem(
                id=ca_id, type="ca", action="added",
                new_text=new_cas[ca_id],
                impact=impact,
                description=f"{ca_id} adicionada: {new_cas[ca_id][:100]}",
            ))
        elif ca_id in old_cas and ca_id not in new_cas:
            delta.removed_cas.append(ca_id)
            delta.items.append(DeltaItem(
                id=ca_id, type="ca", action="removed",
                old_text=old_cas[ca_id],
                impact="high",
                description=f"{ca_id} removida: {old_cas[ca_id][:100]}",
            ))
        else:
            sim = _text_similarity(old_cas[ca_id], new_cas[ca_id])
            if sim < 0.85:
                delta.modified_cas.append(ca_id)
                impact = _assess_impact(ca_id, "modified", new_cas[ca_id])
                delta.items.append(DeltaItem(
                    id=ca_id, type="ca", action="modified",
                    old_text=old_cas[ca_id],
                    new_text=new_cas[ca_id],
                    impact=impact,
                    description=f"{ca_id} modificada (similaridade: {sim:.0%})",
                ))

    # ── Keyword changes ───────────────────────────────────────────────────────
    old_kws = _extract_keywords(old_text)
    new_kws  = _extract_keywords(new_text)
    delta.new_keywords      = list(new_kws  - old_kws)[:10]
    delta.removed_keywords  = list(old_kws - new_kws)[:10]

    # ── Impact level ──────────────────────────────────────────────────────────
    high_items   = [i for i in delta.items if i.impact == "high"]
    medium_items = [i for i in delta.items if i.impact == "medium"]

    if delta.removed_rns or delta.removed_cas or len(high_items) >= 2:
        delta.impact_level = "critical"
    elif high_items or len(delta.added_rns) >= 3:
        delta.impact_level = "high"
    elif medium_items or delta.modified_rns or delta.modified_cas:
        delta.impact_level = "medium"
    elif delta.added_rns or delta.added_cas:
        delta.impact_level = "low"
    else:
        delta.impact_level = "low"

    # ── Affected items ────────────────────────────────────────────────────────
    # What needs to be re-tested / re-analyzed
    delta.affected = list(set(
        delta.modified_rns + delta.removed_rns +
        delta.modified_cas + delta.removed_cas
    ))

    # ── Summary ───────────────────────────────────────────────────────────────
    parts = []
    if delta.added_rns:    parts.append(f"{len(delta.added_rns)} RN(s) adicionada(s)")
    if delta.removed_rns:  parts.append(f"{len(delta.removed_rns)} RN(s) removida(s)")
    if delta.modified_rns: parts.append(f"{len(delta.modified_rns)} RN(s) modificada(s)")
    if delta.added_cas:    parts.append(f"{len(delta.added_cas)} CA(s) adicionada(s)")
    if delta.removed_cas:  parts.append(f"{len(delta.removed_cas)} CA(s) removida(s)")
    if delta.modified_cas: parts.append(f"{len(delta.modified_cas)} CA(s) modificada(s)")
    if delta.new_keywords: parts.append(f"novos termos: {', '.join(delta.new_keywords[:3])}")

    delta.summary = " · ".join(parts) if parts else "Mudanças menores de formatação"

    return delta


# ── Impact propagation ────────────────────────────────────────────────────────

def propagate_impact(delta: VersionDelta, traceability_items: list) -> dict:
    """
    Given a delta and existing traceability items,
    determine what needs to be re-analyzed/re-tested.

    Returns impact report with affected artifacts.
    """
    if not delta.has_changes or not traceability_items:
        return {"affected_tests": [], "affected_automations": [], "re_analysis_needed": False}

    affected_reqs = set(delta.affected)
    affected_tests = []
    affected_automations = []

    for item in traceability_items:
        req_id = item.get("req_id", "")
        if req_id in affected_reqs:
            # This requirement changed — find affected artifacts
            rules     = item.get("rules", [])
            criteria  = item.get("criteria", [])
            scenarios = item.get("scenarios", [])
            risks     = item.get("risks", [])

            for scenario in scenarios:
                affected_tests.append({
                    "scenario":   scenario,
                    "req_id":     req_id,
                    "reason":     f"{req_id} foi modificada",
                    "action":     "Re-executar e validar",
                    "priority":   delta.impact_level,
                })

            for risk in risks:
                affected_automations.append({
                    "automation": risk,
                    "req_id":     req_id,
                    "reason":     f"Risco associado a {req_id} mudou",
                    "action":     "Revisar cobertura de automação",
                    "priority":   delta.impact_level,
                })

    return {
        "affected_reqs":        list(affected_reqs),
        "affected_tests":       affected_tests,
        "affected_automations": affected_automations,
        "re_analysis_needed":   len(affected_reqs) > 0,
        "impact_level":         delta.impact_level,
        "summary":              delta.summary,
    }
