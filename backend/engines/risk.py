"""
engines/risk.py
Parallel Engine: Risk Analysis

Infers technical, security, business, and integration risks.
"""

from models.schemas import NormalizedRequirement, RiskResult, Finding, Severity
from providers.base  import BaseProvider, CompletionRequest
from utils.parser    import extract_json, safe_int

PROMPT_TEMPLATE = """You are an expert QA Risk Analysis Engine.
Analyze this normalized requirement and identify ALL risks.

REQUIREMENT CONTEXT:
Intent: {intent}
Normalized: {normalized}
Actors: {actors}
Actions: {actions}
Conditions: {conditions}
Constraints: {constraints}
Keywords: {keywords}
Complexity: {complexity}

Analyze risks across these dimensions:
- Technical risks (performance, scalability, concurrency, data integrity)
- Security risks (auth, injection, data exposure, privilege escalation)
- Business risks (regulatory, compliance, financial impact, user trust)
- Integration risks (external systems, APIs, timeouts, third-party failures)
- Data risks (loss, corruption, inconsistency, privacy/LGPD/GDPR)
- UX risks (usability failures, accessibility, error feedback)

Return ONLY valid JSON:
{{
  "findings": [
    {{
      "id": "RSK-001",
      "severity": "critical|high|medium|low",
      "title": "risk title",
      "description": "what the risk is, why it exists, what it breaks",
      "suggestion": "concrete mitigation strategy for testing",
      "refs": [],
      "tags": ["technical|security|business|integration|data|ux"]
    }}
  ],
  "score": <0-100, safety score. 100 = no risks detected>,
  "risk_level": "critical|high|medium|low",
  "summary": "one sentence summary of risk landscape"
}}"""


async def run(
    normalized: NormalizedRequirement,
    provider:   BaseProvider,
    max_tokens: int = 1500,
) -> RiskResult:

    prompt = PROMPT_TEMPLATE.format(
        intent=normalized.intent,
        normalized=normalized.normalized,
        actors=", ".join(normalized.actors) or "none",
        actions=", ".join(normalized.actions) or "none",
        conditions=", ".join(normalized.conditions) or "none",
        constraints=", ".join(normalized.constraints) or "none",
        keywords=", ".join(normalized.keywords) or "none",
        complexity=normalized.complexity,
    )

    response = await provider.complete(
        CompletionRequest(prompt=prompt, max_tokens=max_tokens)
    )

    data = extract_json(response.content)

    findings = [
        Finding(
            id=f.get("id", f"RSK-{i+1:03d}"),
            engine="risk",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            suggestion=f.get("suggestion"),
            refs=f.get("refs", []),
            tags=f.get("tags", []),
        )
        for i, f in enumerate(data.get("findings", []))
    ]

    risk_level = data.get("risk_level", "medium")
    if risk_level not in ("critical", "high", "medium", "low"):
        risk_level = "medium"

    return RiskResult(
        findings=findings,
        score=safe_int(data.get("score", 50)),
        risk_level=risk_level,
        summary=data.get("summary", ""),
    )
