"""
engines/traceability.py
Traceability Engine v2 — AI-powered, context-driven

Uses structured RN/CA extraction from the Normalizer (normalized.rns, normalized.cas)
to generate test cases with exact rule and criteria descriptions.

Every RN and CA gets covered. Every risk becomes a negative test case.
"""

import uuid
from typing import Optional
from models.schemas import (
    NormalizedRequirement, AmbiguityResult, RiskResult, RulesResult,
    GapResult, CoverageResult, TraceabilityResult, TraceabilityItem,
    EngineStatus,
)
from providers.base import BaseProvider, CompletionRequest
from utils.parser import extract_json
from utils.requirement_parser import format_for_prompt as format_rn_ca


SYSTEM_PROMPT = """You are a senior QA Engineer and Test Architect.
Generate a complete Requirements Traceability Matrix (RTM) with test cases.

CRITICAL RULES:
1. Every RN listed MUST have at least one CT
2. Every CA listed MUST appear in at least one CT
3. Every Risk finding MUST become a negative test case
4. rn_descriptions and ca_descriptions MUST use the EXACT texts provided
5. CT format: "CT-XXX - RN-XX | CA-XX: Descriptive title"
6. Generate positive AND negative scenarios
7. Steps must be specific and actionable"""


def _build_prompt(
    normalized:    NormalizedRequirement,
    findings_ctx:  str,
    knowledge_ctx: str,
    lang:          str,
) -> str:
    # Build structured RN/CA blocks - limit to avoid token overflow
    rns_block = ""
    if normalized.rns:
        lines = [f"REGRAS DE NEGÓCIO ({len(normalized.rns)} RNs — TODAS devem ter CT):"]
        for rn_id, rn_text in sorted(normalized.rns.items()):
            lines.append(f"  {rn_id}: {rn_text[:200]}")
        rns_block = "\n".join(lines)
    else:
        rns_block = "Extrair RNs do texto do requisito."

    cas_block = ""
    if normalized.cas:
        lines = [f"CRITÉRIOS DE ACEITE ({len(normalized.cas)} CAs — TODOS devem ter CT):"]
        for ca_id, ca_text in sorted(normalized.cas.items()):
            lines.append(f"  {ca_id}: {ca_text[:200]}")
        cas_block = "\n".join(lines)
    else:
        cas_block = "Extrair CAs do texto do requisito."

    rn_count  = len(normalized.rns)
    ca_count  = len(normalized.cas)
    min_cts   = max(rn_count, ca_count, 5)
    min_sc    = max(4, rn_count // 3)

    return f"""Gere uma RTM completa para este requisito com {rn_count} RNs e {ca_count} CAs.

REQUISITO (resumo):
{normalized.intent}
Atores: {", ".join(normalized.actors or [])}

{rns_block}

{cas_block}

FINDINGS DOS ENGINES:
{findings_ctx}

CONTEXTO HISTÓRICO:
{knowledge_ctx}

IDIOMA: {lang}. Chaves JSON em inglês, conteúdo em {lang}.

QUANTIDADE OBRIGATÓRIA:
- Mínimo {min_sc} cenários (positivos + negativos)
- Mínimo {min_cts} casos de teste (CTs) — um por cada RN+CA importante
- Todo risco identificado → 1 CT negativo
- RNs de segurança (acesso, autenticação, autorização) → CTs negativos obrigatórios
- NUNCA retorne 100% em todas as categorias — seja honesto sobre gaps

Retorne APENAS JSON válido:
{{
  "scenarios": [
    {{
      "id": "SC-001",
      "title": "título do cenário",
      "type": "positive",
      "origin_rn": ["RN-01"],
      "origin_ca": ["CA-01"],
      "origin_risk": null,
      "description": "descrição completa",
      "preconditions": ["pré-condição"],
      "test_data": ["dado"],
      "steps": ["1. ação", "2. verificar"],
      "expected_result": "resultado esperado",
      "automated": true,
      "automation_type": "Robot Framework + Browser",
      "priority": "high",
      "coverage_category": "functional",
      "historical_note": null
    }}
  ],
  "test_cases": [
    {{
      "id": "CT-001",
      "scenario_id": "SC-001",
      "title": "CT-001 - RN-01 | CA-01: Exibição do card na Home",
      "type": "functional",
      "rns": ["RN-01"],
      "cas": ["CA-01"],
      "rn_descriptions": {{
        "RN-01": "texto exato da RN-01 conforme extraído acima"
      }},
      "ca_descriptions": {{
        "CA-01": "texto exato do CA-01 conforme extraído acima"
      }},
      "risks": [],
      "gaps": [],
      "preconditions": ["pré-condição"],
      "test_data": {{"campo": "valor"}},
      "steps": ["1. navegar", "2. verificar"],
      "expected_result": "resultado",
      "automated": true,
      "automation_type": "Robot Framework",
      "priority": "high",
      "tags": ["smoke"]
    }}
  ],
  "rtm": [
    {{
      "test_id": "CT-001",
      "rn": "RN-01",
      "ca": "CA-01",
      "title": "Exibição do card na Home",
      "risk": "",
      "gap": "",
      "priority": "high",
      "automated": true
    }}
  ],
  "coverage": {{
    "overall_pct": 75,
    "by_category": {{
      "functional": 85,
      "security": 60,
      "performance": 40,
      "compliance": 70,
      "usability": 50
    }},
    "total_scenarios": {min_sc},
    "positive_scenarios": {min_sc - 2},
    "negative_scenarios": 2,
    "automated_pct": 80,
    "uncovered_rns": [],
    "uncovered_cas": [],
    "missing_scenarios": []
  }},
  "impact_analysis": {{
    "high_risk_areas": [],
    "requires_attention": [],
    "historical_correlations": []
  }},
  "summary": "resumo da cobertura",
  "verdict": "pronto para execução?"
}}

REGRAS OBRIGATÓRIAS:
- Gere {min_cts}+ CTs cobrindo todas as RNs e CAs
- rn_descriptions e ca_descriptions: use o TEXTO EXATO das listas acima
- Formato do título: "CT-XXX - RN-XX | CA-XX: título descritivo"
- RTM: uma linha por CT com test_id, rn, ca, title, risk, gap, priority, automated
- Seja HONESTO na cobertura — identifique gaps reais"""


def _build_findings_context(
    ambiguity: Optional[AmbiguityResult],
    risk:      Optional[RiskResult],
    rules:     Optional[RulesResult],
    gap:       Optional[GapResult],
    coverage:  Optional[CoverageResult],
) -> str:
    lines = []

    if risk and risk.findings:
        lines.append(f"RISKS ({len(risk.findings)}) — {risk.risk_level}:")
        for f in risk.findings[:8]:
            lines.append(f"  [{f.severity.value}] {f.id}: {f.title} — {f.description[:100]}")

    if ambiguity and ambiguity.findings:
        lines.append(f"\nAMBIGUITIES ({len(ambiguity.findings)}):")
        for f in ambiguity.findings[:5]:
            lines.append(f"  [{f.severity.value}] {f.id}: {f.title}")

    if gap and gap.missing:
        lines.append(f"\nGAPS — missing scenarios:")
        for g in gap.missing[:6]:
            lines.append(f"  ✗ {g}")

    return "\n".join(lines) if lines else "No findings."


def _build_knowledge_context(knowledge: Optional[dict]) -> str:
    if not knowledge:
        return "No historical context."

    lines = []
    if knowledge.get("has_history"):
        lines.append(f"Story has {len(knowledge.get('previous_versions', []))} previous versions")
        lines.append(f"Trend: {knowledge.get('version_trend', 'unknown')}")

    defects = knowledge.get("defects_summary", {})
    if defects and defects.get("total", 0) > 0:
        lines.append(f"Historical defects: {defects['total']} total, {defects.get('open', 0)} open")

    kb_entries = knowledge.get("kb_entries", [])
    for e in kb_entries[:4]:
        tags = e.get("tags", [])
        conf = next((t for t in tags if t.startswith("confidence:")), None)
        conf_v = f" (conf: {conf.split(':')[1]})" if conf else ""
        lines.append(f"  [{e.get('category','')}] {e.get('title','')}{conf_v}")

    return "\n".join(lines) if lines else "No historical context."


async def run(
    normalized:  NormalizedRequirement,
    ambiguity:   Optional[AmbiguityResult],
    risk:        Optional[RiskResult],
    rules:       Optional[RulesResult],
    gap:         Optional[GapResult],
    coverage:    Optional[CoverageResult],
    knowledge:   Optional[dict] = None,
    provider:    BaseProvider = None,
    max_tokens:  int = 4000,
    language:    str = "portuguese",
    requirement: str = "",
    project_id:  Optional[str] = None,
) -> TraceabilityResult:

    result = TraceabilityResult()
    lang   = "português" if "port" in language.lower() else "english"

    findings_ctx  = _build_findings_context(ambiguity, risk, rules, gap, coverage)
    knowledge_ctx = _build_knowledge_context(knowledge)
    prompt        = SYSTEM_PROMPT + "\n\n" + _build_prompt(
        normalized, findings_ctx, knowledge_ctx, lang
    )

    try:
        response = await provider.complete(
            CompletionRequest(prompt=prompt, max_tokens=max_tokens)
        )
        data = extract_json(response.content)

        # Build TraceabilityItems from RTM rows
        items = []
        seen_reqs = set()
        for row in data.get("rtm", []):
            req_id = row.get("rn") or row.get("req_id", "REQ-?")
            if req_id not in seen_reqs:
                seen_reqs.add(req_id)
                item = TraceabilityItem(
                    req_id    = req_id,
                    req_title = row.get("title", ""),
                    rules     = [row.get("rn", "")] if row.get("rn") else [],
                    criteria  = [row.get("ca", "")] if row.get("ca") else [],
                    scenarios = [row.get("test_id", "")] if row.get("test_id") else [],
                    risks     = [row.get("risk")] if row.get("risk") else [],
                    gaps      = [row.get("gap")] if row.get("gap") else [],
                    coverage  = "full" if (not row.get("risk") and not row.get("gap")) else "partial",
                    coverage_pct = 100 if (not row.get("risk") and not row.get("gap")) else 60,
                )
                items.append(item)

        cov_data = data.get("coverage", {})
        result.items            = items
        result.overall_coverage = cov_data.get("overall_pct", 0)
        result.uncovered        = (
            cov_data.get("uncovered_rns", []) +
            cov_data.get("uncovered_cas", [])
        )
        result.summary          = data.get("summary", "")
        result.verdict          = data.get("verdict", "")
        result.status           = EngineStatus.DONE
        result.scenarios        = data.get("scenarios", [])
        result.test_cases       = data.get("test_cases", [])
        result.coverage_detail  = cov_data
        result.impact_analysis  = data.get("impact_analysis", {})

        # Store raw RTM for frontend
        result.coverage_detail["_rtm"] = data.get("rtm", [])

    except Exception as e:
        result.status  = EngineStatus.ERROR
        result.summary = f"Traceability engine error: {str(e)}"

    return result
