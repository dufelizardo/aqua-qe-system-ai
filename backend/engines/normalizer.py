"""
engines/normalizer.py
Stage 1: Normalizer Engine

Converts raw requirement text into a structured NormalizedRequirement.
This output feeds ALL parallel engines — so everyone analyzes the same thing.
"""

from models.schemas import NormalizedRequirement
from providers.base  import BaseProvider, CompletionRequest
from utils.parser    import extract_json, safe_int

SYSTEM_PROMPT = """You are a Requirements Normalization Engine for a QA system.
Your job: parse a raw requirement into structured JSON.
Return ONLY valid JSON. No explanation, no markdown fences."""

PROMPT_TEMPLATE = """Analyze this software requirement and return structured JSON:

REQUIREMENT:
{requirement}

CONTEXT (optional):
{context}

{knowledge_context}

Return this exact JSON structure:
{{
  "normalized": "cleaned, unambiguous version of the requirement in one paragraph",
  "intent": "single sentence: what this requirement fundamentally wants to achieve",
  "actors": ["list", "of", "actors/users/systems involved"],
  "actions": ["list", "of", "actions that must happen"],
  "conditions": ["list", "of", "when/if conditions"],
  "constraints": ["list", "of", "limits, rules, non-functionals"],
  "keywords": ["domain", "keywords", "for", "context"],
  "complexity": "low|medium|high"
}}"""


async def run(
    requirement: str,
    context:     str,
    provider:    BaseProvider,
    max_tokens:  int = 800,
    knowledge_context: str = "",
) -> NormalizedRequirement:

    prompt = PROMPT_TEMPLATE.format(
        requirement=requirement,
        context=context or "(none provided)",
        knowledge_context=knowledge_context or "",
    )

    response = await provider.complete(
        CompletionRequest(prompt=SYSTEM_PROMPT + "\n\n" + prompt, max_tokens=max_tokens)
    )

    data = extract_json(response.content)

    return NormalizedRequirement(
        original=requirement,
        normalized=data.get("normalized", requirement),
        intent=data.get("intent", ""),
        actors=data.get("actors", []),
        actions=data.get("actions", []),
        conditions=data.get("conditions", []),
        constraints=data.get("constraints", []),
        keywords=data.get("keywords", []),
        complexity=data.get("complexity", "medium"),
    )
