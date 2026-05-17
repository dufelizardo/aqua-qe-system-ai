"""
engines/coverage.py
Parallel Engine: Coverage Analysis

Determines what test types are needed and what's already inferrable as covered.
"""

from models.schemas import NormalizedRequirement, CoverageResult, Finding, Severity
from providers.base  import BaseProvider, CompletionRequest
from utils.parser    import extract_json, safe_int

PROMPT_TEMPLATE = """You are an expert QA Coverage Analysis Engine.
Analyze what test coverage is needed for this requirement and what might already be covered.

REQUIREMENT CONTEXT:
Intent: {intent}
Normalized: {normalized}
Actors: {actors}
Actions: {actions}
Conditions: {conditions}
Constraints: {constraints}
Complexity: {complexity}

For each dimension below, assess what needs coverage:
- Functional coverage (happy paths, business flows)
- Negative coverage (error handling, validation failures)
- Boundary value coverage (min, max, just outside bounds)
- State coverage (all system states reachable by this feature)
- Security coverage (auth, authz, injection, data exposure)
- Performance coverage (load, latency, throughput SLAs)
- Integration coverage (all external systems touched)
- Regression risk (what existing functionality could break)

Return ONLY valid JSON:
{{
  "covered": [
    "What appears to be adequately specified for testing"
  ],
  "uncovered": [
    "What lacks specification needed for test coverage"
  ],
  "findings": [
    {{
      "id": "COV-001",
      "severity": "critical|high|medium|low|info",
      "title": "coverage finding title",
      "description": "what coverage is missing or at risk",
      "suggestion": "specific test type or scenario to add",
      "refs": [],
      "tags": ["functional|negative|boundary|state|security|performance|integration|regression"]
    }}
  ],
  "score": <0-100, coverage readiness score>,
  "summary": "one sentence summary of coverage analysis"
}}"""


async def run(
    normalized: NormalizedRequirement,
    provider:   BaseProvider,
    max_tokens: int = 1500,
) -> CoverageResult:

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
            id=f.get("id", f"COV-{i+1:03d}"),
            engine="coverage",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            suggestion=f.get("suggestion"),
            refs=f.get("refs", []),
            tags=f.get("tags", []),
        )
        for i, f in enumerate(data.get("findings", []))
    ]

    return CoverageResult(
        findings=findings,
        covered=data.get("covered", []),
        uncovered=data.get("uncovered", []),
        score=safe_int(data.get("score", 50)),
        summary=data.get("summary", ""),
    )
