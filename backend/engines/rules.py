"""
engines/rules.py
Parallel Engine: Business Rules Extraction & Correlation

Extracts explicit and implicit business rules, then checks for contradictions.
"""

from models.schemas import NormalizedRequirement, RulesResult, Finding, Severity
from providers.base  import BaseProvider, CompletionRequest
from utils.parser    import extract_json, safe_int

PROMPT_TEMPLATE = """You are an expert QA Business Rules Engine.
Extract ALL business rules from this requirement — both explicit and implicit.

REQUIREMENT CONTEXT:
Intent: {intent}
Normalized: {normalized}
Actors: {actors}
Actions: {actions}
Conditions: {conditions}
Constraints: {constraints}

Tasks:
1. Extract every business rule (stated or implied)
2. Identify rule conflicts or contradictions
3. Flag rules that are untestable as written
4. Identify missing rules (what SHOULD be a rule but isn't stated)

Return ONLY valid JSON:
{{
  "rules_found": [
    "Plain English statement of each rule found"
  ],
  "findings": [
    {{
      "id": "RUL-001",
      "severity": "critical|high|medium|low",
      "title": "finding title",
      "description": "detail: conflict, untestable rule, or missing rule",
      "suggestion": "how to fix or clarify this rule for testing purposes",
      "refs": [],
      "tags": ["conflict|untestable|missing|implicit|contradiction"]
    }}
  ],
  "score": <0-100, rule clarity/completeness score>,
  "summary": "one sentence summary of business rules analysis"
}}"""


async def run(
    normalized: NormalizedRequirement,
    provider:   BaseProvider,
    max_tokens: int = 1500,
) -> RulesResult:

    prompt = PROMPT_TEMPLATE.format(
        intent=normalized.intent,
        normalized=normalized.normalized,
        actors=", ".join(normalized.actors) or "none",
        actions=", ".join(normalized.actions) or "none",
        conditions=", ".join(normalized.conditions) or "none",
        constraints=", ".join(normalized.constraints) or "none",
    )

    response = await provider.complete(
        CompletionRequest(prompt=prompt, max_tokens=max_tokens)
    )

    data = extract_json(response.content)

    findings = [
        Finding(
            id=f.get("id", f"RUL-{i+1:03d}"),
            engine="rules",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            suggestion=f.get("suggestion"),
            refs=f.get("refs", []),
            tags=f.get("tags", []),
        )
        for i, f in enumerate(data.get("findings", []))
    ]

    return RulesResult(
        findings=findings,
        rules_found=data.get("rules_found", []),
        score=safe_int(data.get("score", 50)),
        summary=data.get("summary", ""),
    )
