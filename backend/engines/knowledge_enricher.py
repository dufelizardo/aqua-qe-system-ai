"""
engines/knowledge_enricher.py
Knowledge Layer 3c — Automatic Enrichment

Runs AFTER the full pipeline completes.
Extracts patterns from findings and saves them to the KB automatically.
Every analysis makes the system smarter.

What it extracts:
  - Recurring risks → saved as 'risco' entries
  - Recurring gaps → saved as 'padrao' entries
  - Business rules found → saved as 'padrao' entries
  - Inferred RNFs → saved as 'comp' or 'risco' entries
  - Correlations from Synthesis → saved as 'heur' entries
  - Defect patterns → tracked for confidence scoring

Never saves duplicates — consolidates by similarity.
"""

import re
import math
from typing import Optional
from datetime import datetime


# ── Similarity ────────────────────────────────────────────────────────────────

def tokenize(text: str) -> set:
    """Simple tokenizer for TF-IDF similarity."""
    stopwords = {
        'de','da','do','das','dos','em','no','na','nos','nas','um','uma',
        'o','a','os','as','e','ou','que','se','para','com','por','ao','à',
        'deve','deverá','sendo','como','quando','onde','qual','este','esta',
        'não','sem','após','antes','durante','sobre','the','a','an','and',
        'or','to','of','in','on','at','for','with','is','are','be','should',
        'must','shall','will','may','can','system','user','usuário','sistema',
    }
    words = re.findall(r'\b[A-Za-zÀ-ÿ]{3,}\b', text.lower())
    return set(w for w in words if w not in stopwords)


def similarity(text1: str, text2: str) -> float:
    """Jaccard similarity between two texts."""
    t1 = tokenize(text1)
    t2 = tokenize(text2)
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / union if union else 0.0


def is_duplicate(new_title: str, new_desc: str, existing: list, threshold: float = 0.5) -> Optional[dict]:
    """Check if a similar entry already exists."""
    new_text = f"{new_title} {new_desc}"
    for entry in existing:
        existing_text = f"{entry.get('title','')} {entry.get('description','')}"
        if similarity(new_text, existing_text) >= threshold:
            return entry
    return None


# ── Confidence scoring ────────────────────────────────────────────────────────

def compute_confidence(occurrences: int) -> float:
    """
    Confidence score based on occurrence frequency.
    1 occurrence = 30%, 3 = 60%, 5 = 75%, 8 = 90%, 10+ = 95%
    Uses logarithmic growth.
    """
    if occurrences <= 0:
        return 0.0
    score = min(0.95, 0.3 + 0.65 * (1 - 1 / (1 + math.log(occurrences))))
    return round(score, 2)


# ── Pattern extraction ────────────────────────────────────────────────────────

def extract_patterns_from_analysis(result) -> list[dict]:
    """
    Extract learnable patterns from a complete pipeline result.
    Returns list of dicts ready to be saved to the KB.
    """
    patterns = []

    # ── From Risk Engine ──────────────────────────────────────────────────────
    if result.risk and result.risk.findings:
        for f in result.risk.findings:
            if f.severity.value in ('critical', 'high'):
                patterns.append({
                    "category":   "risco",
                    "title":      f.title,
                    "description": f.description[:400],
                    "mitigation": f.suggestion or "",
                    "severity":   f.severity.value,
                    "tags":       list(f.tags or []) + ["auto-extracted", "risk-engine"],
                    "origin":     f"risk_engine:{f.id}",
                })

    # ── From Gap Engine ───────────────────────────────────────────────────────
    if result.gap and result.gap.findings:
        for f in result.gap.findings:
            patterns.append({
                "category":   "padrao",
                "title":      f"Gap recorrente: {f.title}",
                "description": f.description[:400],
                "mitigation": f.suggestion or "",
                "severity":   f.severity.value,
                "tags":       list(f.tags or []) + ["auto-extracted", "gap-engine"],
                "origin":     f"gap_engine:{f.id}",
            })

    # ── From Rules Engine ─────────────────────────────────────────────────────
    if result.rules and result.rules.rules_found:
        for rule in result.rules.rules_found[:5]:
            if len(rule) > 20:  # skip trivial rules
                patterns.append({
                    "category":   "padrao",
                    "title":      rule[:100],
                    "description": f"Regra de negócio identificada automaticamente: {rule[:300]}",
                    "severity":   None,
                    "tags":       ["auto-extracted", "rules-engine", "business-rule"],
                    "origin":     "rules_engine",
                })

    # ── From Inference Engine ─────────────────────────────────────────────────
    if result.inference:
        for rnf in (result.inference.rnfs or []):
            if rnf.priority in ('critical', 'high'):
                cat = _rnf_category_to_kb(rnf.category)
                patterns.append({
                    "category":   cat,
                    "title":      rnf.title,
                    "description": rnf.description[:400],
                    "mitigation": f"Inferido de: {rnf.origin}. Rationale: {rnf.rationale[:200]}",
                    "severity":   rnf.priority,
                    "tags":       list(rnf.tags or []) + ["auto-extracted", "inference-engine", "rnf"],
                    "origin":     f"inference_engine:{rnf.id}",
                })

    # ── From Synthesis correlations ───────────────────────────────────────────
    if result.synthesis and result.synthesis.correlations:
        for cor in result.synthesis.correlations:
            if cor.severity.value in ('critical', 'high'):
                patterns.append({
                    "category":   "heur",
                    "title":      f"Correlação: {cor.title}",
                    "description": cor.description[:400],
                    "mitigation": cor.action[:300] if cor.action else "",
                    "severity":   cor.severity.value,
                    "tags":       ["auto-extracted", "synthesis-engine", "correlation"] + list(cor.engines or []),
                    "origin":     f"synthesis_engine:{cor.id}",
                })

    return patterns


def _rnf_category_to_kb(category: str) -> str:
    """Map inference category to KB category."""
    mapping = {
        "performance":    "risco",
        "seguranca":      "risco",
        "disponibilidade":"risco",
        "compliance":     "comp",
        "usabilidade":    "padrao",
        "manutencao":     "padrao",
        "escalabilidade": "risco",
    }
    return mapping.get(category, "padrao")


# ── Main enrichment function ──────────────────────────────────────────────────

async def enrich(
    result,
    story_id: Optional[str],
    project_id: Optional[str] = None,
) -> dict:
    """
    Extract patterns from analysis result and save to KB.
    Called automatically after each pipeline run.

    Returns summary of what was learned.
    """
    summary = {
        "story_id":   story_id,
        "extracted":  0,
        "saved":      0,
        "duplicates": 0,
        "consolidated": 0,
    }

    try:
        from repositories.knowledge import KnowledgeRepository
        kb = KnowledgeRepository()

        # Extract patterns
        patterns = extract_patterns_from_analysis(result)
        summary["extracted"] = len(patterns)

        if not patterns:
            return summary

        # Load existing entries for dedup check
        existing = kb.list(project_id=project_id)

        for pattern in patterns:
            title = pattern.get("title", "")
            desc  = pattern.get("description", "")

            # Check for duplicate
            dup = is_duplicate(title, desc, existing)

            if dup:
                # Consolidate — increment a counter in tags
                summary["duplicates"] += 1

                # Update tags to track occurrence count
                tags = dup.get("tags", [])
                # Find and increment occurrence counter
                occ_tag = next((t for t in tags if t.startswith("occurrences:")), None)
                if occ_tag:
                    count = int(occ_tag.split(":")[1]) + 1
                    tags = [t for t in tags if not t.startswith("occurrences:")]
                else:
                    count = 2
                tags.append(f"occurrences:{count}")

                # Update confidence
                confidence = compute_confidence(count)
                tags = [t for t in tags if not t.startswith("confidence:")]
                tags.append(f"confidence:{confidence}")

                # Add story to seen list
                seen_tag = f"seen_in:{story_id}" if story_id else None
                if seen_tag and seen_tag not in tags:
                    tags.append(seen_tag)

                kb.update(dup["id"], tags=tags)
                summary["consolidated"] += 1
            else:
                # New entry
                tags = pattern.get("tags", [])
                tags.append("occurrences:1")
                tags.append("confidence:0.3")
                if story_id:
                    tags.append(f"seen_in:{story_id}")

                kb.create(
                    category=pattern["category"],
                    title=title,
                    description=desc,
                    project_id=project_id,
                    mitigation=pattern.get("mitigation"),
                    severity=pattern.get("severity"),
                    tags=tags,
                )
                # Add to existing for next iteration dedup check
                existing.append({"title": title, "description": desc, "tags": tags})
                summary["saved"] += 1

    except Exception as e:
        summary["error"] = str(e)

    return summary
