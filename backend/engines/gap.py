"""
engines/gap.py
Parallel Engine: Gap Detection

Finds what's missing: scenarios, edge cases, actors, states, transitions.
"""

from models.schemas import NormalizedRequirement, GapResult, Finding, Severity
from providers.base  import BaseProvider, CompletionRequest
from utils.parser    import extract_json, safe_int

PROMPT_TEMPLATE = """You are an expert QA Gap Detection Engine.
Find everything that is MISSING from this requirement for complete test coverage.

REQUIREMENT CONTEXT:
Intent: {intent}
Normalized: {normalized}
Actors: {actors}
Actions: {actions}
Conditions: {conditions}
Constraints: {constraints}
Complexity: {complexity}

Look for gaps in:
- Missing scenarios (happy path steps not fully described)
- Missing negative/error scenarios (what happens when things go wrong)
- Missing boundary conditions (min/max values, empty, null, overflow)
- Missing actors (who else might interact with this feature)
- Missing state transitions (intermediate states not described)
- Missing non-functional requirements (performance, security, accessibility)
- Missing rollback/recovery scenarios (what happens on failure)
- Missing concurrency scenarios (multiple users, simultaneous actions)
- Missing integration points (external systems not mentioned)
- Missing data validation rules (format, length, type constraints)

Return ONLY valid JSON:
{{
  "missing": [
    "Plain English description of each gap"
  ],
  "findings": [
    {{
      "id": "GAP-001",
      "severity": "critical|high|medium|low",
      "title": "gap title",
      "description": "what is missing and why it matters for test coverage",
      "suggestion": "specific scenario or requirement to add",
      "refs": [],
      "tags": ["scenario|boundary|negative|actor|state|nfr|concurrency|integration|validation"]
    }}
  ],
  "score": <0-100, completeness score. 100 = no gaps>,
  "summary": "one sentence summary of gap analysis"
}}"""


async def run(
    normalized: NormalizedRequirement,
    provider:   BaseProvider,
    max_tokens: int = 1500,
) -> GapResult:

    prompt = PROMPT_TEMPLATE.format(
        intent=normalized.intent,
        normalized=normalized.normalized,
        actors=", ".join(normalized.actors) or "none",
        actions=", ".join(normalized.actions) or "none",
        conditions=", ".join(normalized.conditions) or "none",
        constraints=", ".join(normalized.constraints) or "none",
        complexity=normalized.complexity,
    )

    response = await provider.complete(
        CompletionRequest(prompt=prompt, max_tokens=max_tokens)
    )

    data = extract_json(response.content)

    findings = [
        Finding(
            id=f.get("id", f"GAP-{i+1:03d}"),
            engine="gap",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            suggestion=f.get("suggestion"),
            refs=f.get("refs", []),
            tags=f.get("tags", []),
        )
        for i, f in enumerate(data.get("findings", []))
    ]

    return GapResult(
        findings=findings,
        missing=data.get("missing", []),
        score=safe_int(data.get("score", 50)),
        summary=data.get("summary", ""),
    )
