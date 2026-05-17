"""
engines/synthesis.py
Stage 3: Synthesis Engine

The most important engine. Receives ALL parallel results and produces:
- Cross-engine correlations (the real insights)
- Prioritized action list
- Overall quality score
- Executive verdict

This is what makes the system more than the sum of its parts.
"""

from models.schemas import (
    NormalizedRequirement,
    AmbiguityResult, RiskResult, RulesResult, GapResult, CoverageResult,
    SynthesisResult, Correlation, Severity
)
from providers.base import BaseProvider, CompletionRequest
from utils.parser   import extract_json, safe_int

PROMPT_TEMPLATE = """You are a QA Synthesis Engine — the final stage of a multi-engine analysis pipeline.
You receive outputs from 5 parallel analysis engines and must produce cross-engine insights
that NONE of the individual engines could produce alone.

NORMALIZED REQUIREMENT:
Intent: {intent}
Normalized: {normalized}

ENGINE RESULTS SUMMARY:

AMBIGUITY ENGINE (clarity score: {amb_score}/100):
{amb_summary}
Top findings: {amb_findings}

RISK ENGINE (safety score: {risk_score}/100, level: {risk_level}):
{risk_summary}
Top findings: {risk_findings}

RULES ENGINE (completeness score: {rules_score}/100):
{rules_summary}
Rules found: {rules_found}
Top findings: {rules_findings}

GAP ENGINE (completeness score: {gap_score}/100):
{gap_summary}
Key gaps: {gaps_missing}

COVERAGE ENGINE (readiness score: {cov_score}/100):
{cov_summary}
Uncovered areas: {cov_uncovered}

Your job: find the CORRELATIONS between engines. Examples of what to look for:
- An ambiguity that directly CAUSES a risk
- A missing rule that creates a coverage gap
- A gap that amplifies a risk (e.g., no error handling + security risk = critical)
- Rules that contradict coverage expectations
- Ambiguities that make entire test scenarios untestable

Return ONLY valid JSON:
{{
  "correlations": [
    {{
      "id": "COR-001",
      "engines": ["ambiguity", "risk"],
      "severity": "critical|high|medium|low",
      "title": "correlation title — what two things connect",
      "description": "the insight: WHY this combination matters more than each finding alone",
      "action": "specific, concrete action to resolve this correlation"
    }}
  ],
  "top_actions": [
    "Prioritized action #1 (most critical)",
    "Prioritized action #2",
    "Prioritized action #3",
    "Prioritized action #4",
    "Prioritized action #5"
  ],
  "overall_score": <0-100, weighted quality score considering all engines>,
  "verdict": "one crisp sentence: the bottom line on this requirement's readiness for testing",
  "summary": "2-3 sentences: executive summary of the full analysis"
}}"""


async def run(
    normalized: NormalizedRequirement,
    ambiguity:  AmbiguityResult,
    risk:       RiskResult,
    rules:      RulesResult,
    gap:        GapResult,
    coverage:   CoverageResult,
    provider:   BaseProvider,
    max_tokens: int = 1500,
) -> SynthesisResult:

    def top_findings(result, n=3) -> str:
        findings = result.findings[:n]
        if not findings:
            return "(none)"
        return "; ".join(f"[{f.severity.value}] {f.title}" for f in findings)

    prompt = PROMPT_TEMPLATE.format(
        intent=normalized.intent,
        normalized=normalized.normalized,
        amb_score=ambiguity.score,
        amb_summary=ambiguity.summary,
        amb_findings=top_findings(ambiguity),
        risk_score=risk.score,
        risk_level=risk.risk_level,
        risk_summary=risk.summary,
        risk_findings=top_findings(risk),
        rules_score=rules.score,
        rules_summary=rules.summary,
        rules_found="; ".join(rules.rules_found[:5]) or "(none)",
        rules_findings=top_findings(rules),
        gap_score=gap.score,
        gap_summary=gap.summary,
        gaps_missing="; ".join(gap.missing[:5]) or "(none)",
        cov_score=coverage.score,
        cov_summary=coverage.summary,
        cov_uncovered="; ".join(coverage.uncovered[:5]) or "(none)",
    )

    response = await provider.complete(
        CompletionRequest(prompt=prompt, max_tokens=max_tokens)
    )

    data = extract_json(response.content)

    correlations = [
        Correlation(
            id=c.get("id", f"COR-{i+1:03d}"),
            engines=c.get("engines", []),
            severity=Severity(c.get("severity", "medium")),
            title=c.get("title", ""),
            description=c.get("description", ""),
            action=c.get("action", ""),
        )
        for i, c in enumerate(data.get("correlations", []))
    ]

    return SynthesisResult(
        overall_score=safe_int(data.get("overall_score", 50)),
        verdict=data.get("verdict", ""),
        correlations=correlations,
        top_actions=data.get("top_actions", []),
        summary=data.get("summary", ""),
    )
