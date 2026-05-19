"""
engines/requirements_inference.py
Requirements Inference Engine

Uses AI to infer implicit Functional (RF) and Non-Functional (RNF)
requirements hidden inside RNs, CAs, gaps and risks.

Runs in parallel with the 5 main engines, after Normalizer.
Does NOT replace them — adds a new layer of insight.

Output feeds:
  - Artifact Generator (PO profile — CAs, business value)
  - Synthesis Engine (via context)
  - Frontend module (new dedicated view)
"""

import uuid
from typing import Optional
from models.schemas import (
    NormalizedRequirement, AmbiguityResult, RiskResult,
    RulesResult, GapResult, InferenceResult, InferredRequirement,
    EngineStatus,
)
from providers.base import BaseProvider, CompletionRequest
from utils.parser import extract_json


SYSTEM_PROMPT = """You are a senior Requirements Engineer and QA Architect.
Your job is to read a software requirement and infer ALL implicit requirements
that are NOT explicitly written but MUST exist for the system to work correctly.

Focus on:
- Functional requirements hidden inside business rules
- Non-functional requirements implied by the context
- Requirements that developers would need to implement but are not stated
- Compliance/regulatory requirements implied by the domain
- Security requirements implied by the data and user profiles"""


PROMPT_TEMPLATE = """Analyze this requirement and ALL engine findings below.
Infer ALL implicit Functional (RF) and Non-Functional (RNF) requirements.

REQUIREMENT:
{requirement}

ENGINE FINDINGS:
{findings_context}

{language_instruction}

Return ONLY valid JSON with this exact structure:
{{
  "rfs": [
    {{
      "id": "RF-001",
      "type": "RF",
      "category": "funcional",
      "title": "Short title of the inferred requirement",
      "description": "Full description of what must exist",
      "rationale": "Why this is inferred — which RN/CA/gap/risk implies this",
      "origin": "RN-01 / CA-03 / GAP-001 / RSK-002",
      "priority": "high",
      "tags": ["auth", "security"]
    }}
  ],
  "rnfs": [
    {{
      "id": "RNF-001",
      "type": "RNF",
      "category": "seguranca",
      "title": "Short title",
      "description": "Full description",
      "rationale": "Why inferred",
      "origin": "RSK-001",
      "priority": "critical",
      "tags": ["security", "compliance"]
    }}
  ],
  "missing": [
    "Brief description of requirement that should exist but is completely absent"
  ],
  "summary": "2-3 sentence summary of what was inferred and why it matters",
  "verdict": "One sentence assessment: ready for dev? what's missing?"
}}

Categories for RF: funcional, integracao, dados, interface, negocio
Categories for RNF: performance, seguranca, disponibilidade, compliance, usabilidade, manutencao, escalabilidade

Generate minimum 4 RFs and 4 RNFs. Be specific and actionable."""


def _build_findings_context(
    ambiguity: Optional[AmbiguityResult],
    risk:      Optional[RiskResult],
    rules:     Optional[RulesResult],
    gap:       Optional[GapResult],
) -> str:
    lines = []

    if rules and rules.rules_found:
        lines.append("BUSINESS RULES FOUND:")
        for r in rules.rules_found[:8]:
            lines.append(f"  → {r}")

    if ambiguity and ambiguity.findings:
        lines.append(f"\nAMBIGUITIES ({len(ambiguity.findings)}):")
        for f in ambiguity.findings[:5]:
            lines.append(f"  [{f.severity.value}] {f.title}: {f.suggestion or f.description[:100]}")

    if risk and risk.findings:
        lines.append(f"\nRISKS ({len(risk.findings)}) — level: {risk.risk_level}:")
        for f in risk.findings[:5]:
            lines.append(f"  [{f.severity.value}] {f.title}: {f.description[:100]}")

    if gap and gap.missing:
        lines.append(f"\nIDENTIFIED GAPS:")
        for g in gap.missing[:6]:
            lines.append(f"  ✗ {g}")

    return "\n".join(lines) if lines else "No engine findings available."


async def run(
    normalized:  NormalizedRequirement,
    ambiguity:   Optional[AmbiguityResult],
    risk:        Optional[RiskResult],
    rules:       Optional[RulesResult],
    gap:         Optional[GapResult],
    provider:    BaseProvider,
    max_tokens:  int = 2000,
    language:    str = "portuguese",
) -> InferenceResult:

    result = InferenceResult()
    lang_instruction = (
        f"IMPORTANT: Return ALL text fields in {language}. Keep JSON keys in English."
    )

    findings_ctx = _build_findings_context(ambiguity, risk, rules, gap)

    prompt = SYSTEM_PROMPT + "\n\n" + PROMPT_TEMPLATE.format(
        requirement=normalized.original or normalized.normalized,
        findings_context=findings_ctx,
        language_instruction=lang_instruction,
    )

    try:
        response = await provider.complete(
            CompletionRequest(prompt=prompt, max_tokens=max_tokens)
        )
        data = extract_json(response.content)

        # Parse RFs
        for item in data.get("rfs", []):
            result.rfs.append(InferredRequirement(
                id=item.get("id", f"RF-{uuid.uuid4().hex[:3].upper()}"),
                type="RF",
                category=item.get("category", "funcional"),
                title=item.get("title", ""),
                description=item.get("description", ""),
                rationale=item.get("rationale", ""),
                origin=item.get("origin", ""),
                priority=item.get("priority", "medium"),
                tags=item.get("tags", []),
            ))

        # Parse RNFs
        for item in data.get("rnfs", []):
            result.rnfs.append(InferredRequirement(
                id=item.get("id", f"RNF-{uuid.uuid4().hex[:3].upper()}"),
                type="RNF",
                category=item.get("category", "performance"),
                title=item.get("title", ""),
                description=item.get("description", ""),
                rationale=item.get("rationale", ""),
                origin=item.get("origin", ""),
                priority=item.get("priority", "medium"),
                tags=item.get("tags", []),
            ))

        result.missing = data.get("missing", [])
        result.summary = data.get("summary", "")
        result.verdict = data.get("verdict", "")
        result.total   = len(result.rfs) + len(result.rnfs)
        result.status  = EngineStatus.DONE

    except Exception as e:
        result.status  = EngineStatus.ERROR
        result.summary = f"Inference engine error: {str(e)}"

    return result
