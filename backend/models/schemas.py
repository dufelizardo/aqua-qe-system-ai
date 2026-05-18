"""
models/schemas.py
Data contracts for the entire QA system.
All engines speak this language.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


# ── Enums ────────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class EngineStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    DONE     = "done"
    ERROR    = "error"


# ── Input ────────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    """Payload sent by the frontend to trigger a full analysis."""
    requirement: str = Field(..., min_length=10, description="Raw requirement text")
    context:     Optional[str] = Field(None, description="Additional context, rules, history")
    project_id:  Optional[str] = Field(None, description="Project identifier for traceability")
    engines:     Optional[list[str]] = Field(
        default=None,
        description="Specific engines to run. None = run all."
    )


# ── Normalizer output ────────────────────────────────────────────────────────

class NormalizedRequirement(BaseModel):
    """Output of the Normalizer Engine. Feeds all parallel engines."""
    original:       str
    normalized:     str            # cleaned, structured version
    intent:         str            # single sentence: what this requirement wants
    actors:         list[str]      # who is involved
    actions:        list[str]      # what must happen
    conditions:     list[str]      # when / under what conditions
    constraints:    list[str]      # limits, rules, non-functionals
    keywords:       list[str]      # domain keywords for context
    complexity:     Literal["low", "medium", "high"]
    # Structured extraction — populated by requirement_parser
    rns:            dict = {}      # {"RN-01": "full description text", ...}
    cas:            dict = {}      # {"CA-01": "full description text", ...}


# ── Per-engine findings ──────────────────────────────────────────────────────

class Finding(BaseModel):
    id:          str
    engine:      str
    severity:    Severity
    title:       str
    description: str
    suggestion:  Optional[str] = None
    refs:        list[str] = []
    tags:        list[str] = []


class AmbiguityResult(BaseModel):
    engine:      str = "ambiguity"
    status:      EngineStatus = EngineStatus.DONE
    findings:    list[Finding] = []
    score:       int = Field(ge=0, le=100)   # clarity score
    summary:     str


class RiskResult(BaseModel):
    engine:      str = "risk"
    status:      EngineStatus = EngineStatus.DONE
    findings:    list[Finding] = []
    score:       int = Field(ge=0, le=100)   # risk score (lower = riskier)
    summary:     str
    risk_level:  Literal["critical", "high", "medium", "low"]


class RulesResult(BaseModel):
    engine:      str = "rules"
    status:      EngineStatus = EngineStatus.DONE
    findings:    list[Finding] = []
    score:       int = Field(ge=0, le=100)
    summary:     str
    rules_found: list[str] = []


class GapResult(BaseModel):
    engine:      str = "gap"
    status:      EngineStatus = EngineStatus.DONE
    findings:    list[Finding] = []
    score:       int = Field(ge=0, le=100)   # completeness score
    summary:     str
    missing:     list[str] = []              # explicit list of gaps


class CoverageResult(BaseModel):
    engine:      str = "coverage"
    status:      EngineStatus = EngineStatus.DONE
    findings:    list[Finding] = []
    score:       int = Field(ge=0, le=100)   # coverage score
    summary:     str
    covered:     list[str] = []
    uncovered:   list[str] = []


# ── Synthesis ────────────────────────────────────────────────────────────────

class Correlation(BaseModel):
    """A meaningful cross-engine correlation found by the Synthesis Engine."""
    id:          str
    engines:     list[str]       # which engines contributed
    severity:    Severity
    title:       str
    description: str             # the insight: why this combination matters
    action:      str             # what to do about it


class SynthesisResult(BaseModel):
    engine:        str = "synthesis"
    overall_score: int = Field(ge=0, le=100)
    verdict:       str                       # one-line verdict
    correlations:  list[Correlation] = []    # cross-engine insights
    top_actions:   list[str] = []            # prioritized action list
    summary:       str


# ── Full Analysis Response ───────────────────────────────────────────────────

class EngineTimings(BaseModel):
    normalizer: Optional[float] = None
    ambiguity:  Optional[float] = None
    risk:       Optional[float] = None
    rules:      Optional[float] = None
    gap:        Optional[float] = None
    coverage:   Optional[float] = None
    synthesis:  Optional[float] = None
    total:      Optional[float] = None


class TraceabilityItem(BaseModel):
    """A single traceability link between requirement and another artifact."""
    req_id:       str
    req_title:    str
    rules:        list[str] = []
    criteria:     list[str] = []
    scenarios:    list[str] = []
    risks:        list[str] = []
    gaps:         list[str] = []
    coverage:     str = "none"   # full | partial | none
    coverage_pct: int = 0


class TraceabilityResult(BaseModel):
    engine:           str = "traceability"
    status:           EngineStatus = EngineStatus.DONE
    items:            list[TraceabilityItem] = []
    overall_coverage: int = 0
    uncovered:        list[str] = []
    summary:          str = ""
    verdict:          str = ""
    # v2 rich fields
    scenarios:        list[dict] = []
    test_cases:       list[dict] = []
    coverage_detail:  dict = {}
    impact_analysis:  dict = {}


class ArtifactItem(BaseModel):
    """A single generated artifact."""
    id:          str
    profile:     str   # qa | dev | po | audit
    type:        str   # gherkin | robot | test_cases | evidence | skeleton | gap_analysis | ca | business_value | risk_report | rtm
    title:       str
    content:     str
    format:      str   # markdown | robot | gherkin | json | csv | html
    story_id:    Optional[str] = None
    version:     Optional[int] = None
    refs:        list[str] = []  # finding IDs used to generate this artifact


class ArtifactResult(BaseModel):
    """Full artifact generation result — all profiles."""
    engine:      str = "artifact_generator"
    status:      EngineStatus = EngineStatus.DONE
    story_id:    Optional[str] = None
    artifacts:   list[ArtifactItem] = []
    summary:     str = ""


class InferredRequirement(BaseModel):
    """A single inferred requirement (RF or RNF)."""
    id:          str
    type:        str   # RF | RNF
    category:    str   # funcional | performance | seguranca | disponibilidade | compliance | usabilidade | dados
    title:       str
    description: str
    rationale:   str   # why this was inferred
    origin:      str   # which RN/CA/gap/risk originated this
    priority:    str   # critical | high | medium | low
    tags:        list[str] = []


class InferenceResult(BaseModel):
    """Full output of the Requirements Inference Engine."""
    engine:      str = "requirements_inference"
    status:      EngineStatus = EngineStatus.DONE
    rfs:         list[InferredRequirement] = []   # Functional requirements
    rnfs:        list[InferredRequirement] = []   # Non-functional requirements
    missing:     list[str] = []                   # Requirements that should exist but don't
    total:       int = 0
    summary:     str = ""
    verdict:     str = ""


class AnalysisResponse(BaseModel):
    """Full response returned to the frontend."""
    request_id:  str
    project_id:  Optional[str]
    status:      EngineStatus

    # pipeline stages
    normalized:     Optional[NormalizedRequirement] = None
    ambiguity:      Optional[AmbiguityResult]       = None
    risk:           Optional[RiskResult]            = None
    rules:          Optional[RulesResult]           = None
    gap:            Optional[GapResult]             = None
    coverage:       Optional[CoverageResult]        = None
    traceability:   Optional[TraceabilityResult]    = None
    knowledge:      Optional[dict]                  = None
    inference:      Optional[InferenceResult]       = None
    artifacts:      Optional[ArtifactResult]        = None
    synthesis:      Optional[SynthesisResult]       = None

    timings:     EngineTimings = EngineTimings()
    error:       Optional[str] = None


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:   str
    provider: str
    model:    str
    version:  str = "1.0.0"
