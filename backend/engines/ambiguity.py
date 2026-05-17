"""
engines/ambiguity.py
Parallel Engine: Ambiguity Detection

Identifies vague terms, undefined conditions, and multiple interpretations.
Receives NormalizedRequirement — never raw text.
"""

from models.schemas import NormalizedRequirement, AmbiguityResult, Finding, Severity
from providers.base  import BaseProvider, CompletionRequest
from utils.parser    import extract_json, safe_int

PROMPT_TEMPLATE = """You are an expert QA Ambiguity Detection Engine.
Analyze this normalized requirement and identify ALL ambiguities.

REQUIREMENT CONTEXT:
Intent: {intent}
Normalized: {normalized}
Actors: {actors}
Actions: {actions}
Conditions: {conditions}
Constraints: {constraints}

Find ambiguities in these categories:
- Vague terms (e.g., "quickly", "easy", "large", "many", "appropriate")
- Missing quantifiers (no numbers, no thresholds, no time bounds)
- Undefined actor behavior (actor exists but behavior not specified)
- Multiple valid interpretations (same sentence can mean two different things)
- Implicit assumptions (things assumed but not stated)
- Missing error/exception states

Return ONLY valid JSON:
{{
  "findings": [
    {{
      "id": "AMB-001",
      "severity": "critical|high|medium|low",
      "title": "short title",
      "description": "what is ambiguous and why it matters for testing",
      "suggestion": "concrete way to remove this ambiguity",
      "refs": [],
      "tags": ["vague-term|missing-quantifier|implicit-assumption|..."]
    }}
  ],
  "score": <0-100, clarity score. 100 = perfectly clear>,
  "summary": "one sentence summary of ambiguity analysis"
}}"""


async def run(
    normalized: NormalizedRequirement,
    provider:   BaseProvider,
    max_tokens: int = 1500,
) -> AmbiguityResult:

    prompt = PROMPT_TEMPLATE.format(
        intent=normalized.intent,
        normalized=normalized.normalized,
        actors=", ".join(normalized.actors) or "none identified",
        actions=", ".join(normalized.actions) or "none identified",
        conditions=", ".join(normalized.conditions) or "none identified",
        constraints=", ".join(normalized.constraints) or "none identified",
    )

    response = await provider.complete(
        CompletionRequest(prompt=prompt, max_tokens=max_tokens)
    )

    data = extract_json(response.content)

    findings = [
        Finding(
            id=f.get("id", f"AMB-{i+1:03d}"),
            engine="ambiguity",
            severity=Severity(f.get("severity", "medium")),
            title=f.get("title", ""),
            description=f.get("description", ""),
            suggestion=f.get("suggestion"),
            refs=f.get("refs", []),
            tags=f.get("tags", []),
        )
        for i, f in enumerate(data.get("findings", []))
    ]

    return AmbiguityResult(
        findings=findings,
        score=safe_int(data.get("score", 50)),
        summary=data.get("summary", ""),
    )
