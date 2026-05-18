"""
main.py
FastAPI application — routes for pipeline, history, projects and knowledge.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from models.schemas    import AnalysisRequest, AnalysisResponse, HealthResponse, EngineStatus
from models.database   import init_db
from orchestrator      import analyze
from providers.factory import get_provider
from utils.config      import settings
from repositories.analysis  import AnalysisRepository
from repositories.project   import ProjectRepository
from repositories.knowledge import KnowledgeRepository

app = FastAPI(
    title="QA Intelligence System",
    description="Multi-engine QA analysis pipeline with persistence",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

analysis_repo  = AnalysisRepository()
project_repo   = ProjectRepository()
knowledge_repo = KnowledgeRepository()


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    provider = get_provider()
    ok = await provider.health_check()
    return HealthResponse(
        status="healthy" if ok else "degraded",
        provider=provider.provider_name,
        model=provider.model_name,
    )


@app.get("/api/v1/config")
async def get_config():
    provider = get_provider()
    return {
        "provider":    provider.provider_name,
        "model":       provider.model_name,
        "env":         settings.APP_ENV,
        "db_path":     settings.DB_PATH,
        "engines":     ["normalizer","ambiguity","risk","rules","gap","coverage","synthesis"],
        "language":    settings.ENGINE_LANGUAGE,
    }


@app.post("/api/v1/analyze", response_model=AnalysisResponse)
async def analyze_requirement(request: AnalysisRequest):
    result = await analyze(request)
    if result.status == EngineStatus.ERROR and not result.normalized:
        raise HTTPException(status_code=500, detail=result.error)
    return result


@app.post("/api/v1/analyze/quick")
async def analyze_quick(request: AnalysisRequest):
    from engines import normalizer
    provider = get_provider()
    try:
        normalized = await normalizer.run(
            requirement=request.requirement,
            context=request.context or "",
            provider=provider,
        )
        return {"status": "done", "normalized": normalized.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/history")
async def get_history(project_id: Optional[str] = None, limit: int = 20):
    return analysis_repo.list_recent(project_id=project_id, limit=limit)


@app.get("/api/v1/history/{analysis_id}")
async def get_analysis(analysis_id: str):
    result = analysis_repo.get(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@app.get("/api/v1/stories/{story_id}/history")
async def get_story_history(story_id: str):
    return analysis_repo.list_by_story(story_id)


@app.get("/api/v1/stories/{story_id}/compare")
async def compare_versions(story_id: str, v1: int = 1, v2: int = 2):
    return analysis_repo.compare_versions(story_id, v1, v2)


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class StoryCreate(BaseModel):
    title: str
    external_id: Optional[str] = None

class KnowledgeCreate(BaseModel):
    category: str
    title: str
    description: str
    project_id: Optional[str] = None
    context: Optional[str] = None
    mitigation: Optional[str] = None
    severity: Optional[str] = None
    tags: Optional[list[str]] = []


@app.get("/api/v1/projects")
async def list_projects():
    return project_repo.list_projects()


@app.post("/api/v1/projects")
async def create_project(body: ProjectCreate):
    return project_repo.create_project(body.name, body.description)


@app.get("/api/v1/projects/{project_id}/stories")
async def list_stories(project_id: str):
    return project_repo.list_stories(project_id)


@app.post("/api/v1/projects/{project_id}/stories")
async def create_story(project_id: str, body: StoryCreate):
    return project_repo.create_story(project_id, body.title, body.external_id)


@app.get("/api/v1/knowledge")
async def list_knowledge(project_id: Optional[str] = None, category: Optional[str] = None):
    return knowledge_repo.list(project_id=project_id, category=category)


@app.post("/api/v1/knowledge")
async def create_knowledge(body: KnowledgeCreate):
    return knowledge_repo.create(
        category=body.category, title=body.title, description=body.description,
        project_id=body.project_id, context=body.context,
        mitigation=body.mitigation, severity=body.severity, tags=body.tags,
    )


@app.get("/api/v1/knowledge/search")
async def search_knowledge(q: str, project_id: Optional[str] = None):
    return knowledge_repo.search(q, project_id=project_id)


@app.delete("/api/v1/knowledge/{knowledge_id}")
async def delete_knowledge(knowledge_id: str):
    knowledge_repo.delete(knowledge_id)
    return {"deleted": knowledge_id}


@app.get("/")
async def root():
    return {"message": "QA Intelligence System v2.0", "docs": "/docs"}


# ── Versioning ────────────────────────────────────────────────────────────────
from utils.versioning  import check_version, get_story_versions
from utils.id_detector import detect_story_id

@app.post("/api/v1/check-version")
async def check_requirement_version(request: AnalysisRequest):
    """
    Check if this requirement has been analyzed before.
    Call this BEFORE /analyze to detect existing versions.
    Returns VersionInfo for the Hub to show the version dialog.
    """
    info = check_version(request.requirement)
    return info.to_dict()


@app.get("/api/v1/stories/{story_id}/versions")
async def get_story_version_list(story_id: str):
    """All versions of a story with scores for comparison."""
    versions = get_story_versions(story_id)
    return {
        "story_id": story_id,
        "total":    len(versions),
        "versions": versions,
    }


@app.get("/api/v1/detect-id")
async def detect_id(text: str):
    """Detect story ID from requirement text."""
    story_id = detect_story_id(text)
    return {"story_id": story_id, "detected": story_id is not None}


# ── Story Links ───────────────────────────────────────────────────────────────
from repositories.story_links import StoryLinksRepository

story_links_repo = StoryLinksRepository()

class StoryLinkCreate(BaseModel):
    parent_id:   str
    child_id:    str
    link_type:   Optional[str] = "improvement"
    description: Optional[str] = None

class KnowledgeStoryLink(BaseModel):
    knowledge_id: str
    story_id:     str
    note:         Optional[str] = None


@app.get("/api/v1/stories/{story_id}/family")
async def get_story_family(story_id: str):
    """Get full family tree: parent, children, siblings."""
    return story_links_repo.get_family(story_id)


@app.get("/api/v1/stories/{story_id}/knowledge")
async def get_story_knowledge(story_id: str):
    """Get all knowledge entries linked to this story (direct + inherited)."""
    return story_links_repo.get_story_context(story_id)


@app.post("/api/v1/story-links")
async def create_story_link(body: StoryLinkCreate):
    """Link a child story (improvement) to a parent story."""
    return story_links_repo.link_stories(
        parent_id=body.parent_id,
        child_id=body.child_id,
        link_type=body.link_type,
        description=body.description,
    )


@app.delete("/api/v1/story-links")
async def remove_story_link(parent_id: str, child_id: str):
    story_links_repo.unlink_stories(parent_id, child_id)
    return {"unlinked": True}


@app.post("/api/v1/knowledge-story-links")
async def link_knowledge_to_story(body: KnowledgeStoryLink):
    """Link a knowledge entry directly to a story ID."""
    return story_links_repo.link_knowledge_to_story(
        knowledge_id=body.knowledge_id,
        story_id=body.story_id,
        note=body.note,
    )


@app.delete("/api/v1/knowledge-story-links")
async def unlink_knowledge_from_story(knowledge_id: str, story_id: str):
    story_links_repo.unlink_knowledge_from_story(knowledge_id, story_id)
    return {"unlinked": True}


# ── Defects ───────────────────────────────────────────────────────────────────
from repositories.defects import DefectsRepository

defects_repo = DefectsRepository()

class DefectCreate(BaseModel):
    story_id:          str
    title:             str
    severity:          str                    # critical|high|medium|low
    defect_type:       str                    # qa|production|regression
    jira_id:           Optional[str] = None
    description:       Optional[str] = None
    story_version:     Optional[int] = None
    sprint_found:      Optional[str] = None
    sprint_fixed:      Optional[str] = None
    fixed_in_version:  Optional[int] = None
    evidence:          Optional[str] = None
    status:            Optional[str] = "open"

class DefectStatusUpdate(BaseModel):
    status:            str
    sprint_fixed:      Optional[str] = None
    fixed_in_version:  Optional[int] = None


@app.get("/api/v1/stories/{story_id}/defects")
async def list_story_defects(story_id: str):
    """List all defects for a story."""
    return defects_repo.list_by_story(story_id)


@app.get("/api/v1/stories/{story_id}/defects/summary")
async def get_defects_summary(story_id: str):
    """Summary of defects — used by the pipeline and Hub."""
    return defects_repo.get_summary(story_id)


@app.post("/api/v1/defects")
async def create_defect(body: DefectCreate):
    """Register a new defect linked to a story."""
    return defects_repo.create(
        story_id=body.story_id,
        title=body.title,
        severity=body.severity,
        defect_type=body.defect_type,
        jira_id=body.jira_id,
        description=body.description,
        story_version=body.story_version,
        sprint_found=body.sprint_found,
        sprint_fixed=body.sprint_fixed,
        fixed_in_version=body.fixed_in_version,
        evidence=body.evidence,
        status=body.status or "open",
    )


@app.patch("/api/v1/defects/{defect_id}/status")
async def update_defect_status(defect_id: str, body: DefectStatusUpdate):
    """Update defect status (open/fixed/reopened/wont_fix)."""
    result = defects_repo.update_status(
        defect_id=defect_id,
        status=body.status,
        sprint_fixed=body.sprint_fixed,
        fixed_in_version=body.fixed_in_version,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Defect not found")
    return result


@app.delete("/api/v1/defects/{defect_id}")
async def delete_defect(defect_id: str):
    defects_repo.delete(defect_id)
    return {"deleted": defect_id}


@app.get("/api/v1/defects/open")
async def list_open_defects(story_id: Optional[str] = None):
    """List all open/reopened defects, optional story filter."""
    return defects_repo.list_open(story_id=story_id)


# ── Artifact Generation ───────────────────────────────────────────────────────
import engines.artifact_generator as artifact_gen_mod

class ArtifactRequest(BaseModel):
    analysis_id: str                          # ID of existing analysis
    profiles:    Optional[list[str]] = None   # None = all profiles


@app.post("/api/v1/artifacts/generate")
async def generate_artifacts(body: ArtifactRequest):
    """
    Generate artifacts from an existing analysis.
    Fetches full pipeline result from DB and runs artifact generator.
    """
    # Load analysis from DB
    full = analysis_repo.get(body.analysis_id)
    if not full:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result_data = full.get("result")
    if not result_data:
        raise HTTPException(status_code=422, detail="Analysis has no result data")

    # Reconstruct pipeline objects from stored JSON
    from models.schemas import (
        NormalizedRequirement, AmbiguityResult, RiskResult,
        RulesResult, GapResult, CoverageResult,
        TraceabilityResult, SynthesisResult,
    )

    def safe_parse(model, data):
        try:
            return model(**data) if data else None
        except Exception:
            return None

    normalized   = safe_parse(NormalizedRequirement, result_data.get("normalized"))
    ambiguity    = safe_parse(AmbiguityResult,        result_data.get("ambiguity"))
    risk         = safe_parse(RiskResult,             result_data.get("risk"))
    rules_result = safe_parse(RulesResult,            result_data.get("rules"))
    gap          = safe_parse(GapResult,              result_data.get("gap"))
    cov          = safe_parse(CoverageResult,         result_data.get("coverage"))
    tra          = safe_parse(TraceabilityResult,     result_data.get("traceability"))
    synth        = safe_parse(SynthesisResult,        result_data.get("synthesis"))
    knowledge    = result_data.get("knowledge")

    # Parse inference if available
    try:
        from models.schemas import InferenceResult
        inf = safe_parse(InferenceResult, result_data.get("inference"))
    except Exception:
        inf = None

    if not normalized:
        raise HTTPException(status_code=422, detail="Normalized data missing from analysis")

    provider = get_provider()
    artifacts = await artifact_gen_mod.run(
        normalized=normalized,
        ambiguity=ambiguity,
        risk=risk,
        rules=rules_result,
        gap=gap,
        coverage=cov,
        traceability=tra,
        inference=inf,
        synthesis=synth,
        knowledge=knowledge,
        provider=provider,
        max_tokens=settings.ENGINE_MAX_TOKENS,
        language=settings.ENGINE_LANGUAGE,
        story_id=full.get("story_id"),
        profiles=body.profiles,
    )

    # ── Save artifacts back to the analysis record ────────────────────────────
    try:
        import json
        from models.database import get_connection, analyses
        from sqlalchemy import update as sa_update

        # Merge artifacts into existing result_json
        result_data["artifacts"] = artifacts.model_dump(mode='json')
        new_json = json.dumps(result_data, default=str)

        with get_connection() as conn:
            conn.execute(
                sa_update(analyses)
                .where(analyses.c.id == body.analysis_id)
                .values(result_json=new_json)
            )
            conn.commit()
    except Exception as e:
        # Never fail the response because of a save error
        pass

    return artifacts


@app.get("/api/v1/artifacts/{analysis_id}")
async def get_artifacts(analysis_id: str, profile: Optional[str] = None):
    """
    Get previously generated artifacts for an analysis.
    Optional profile filter: qa | dev | po | audit
    """
    full = analysis_repo.get(analysis_id)
    if not full:
        raise HTTPException(status_code=404, detail="Analysis not found")

    arts = full.get("result", {}).get("artifacts")
    if not arts:
        raise HTTPException(status_code=404, detail="No artifacts generated for this analysis")

    items = arts.get("artifacts", [])
    if profile:
        items = [a for a in items if a.get("profile") == profile]

    return {"analysis_id": analysis_id, "total": len(items), "artifacts": items}


# ── Knowledge Layer 3c ────────────────────────────────────────────────────────
@app.get("/api/v1/knowledge/stats")
async def knowledge_stats(project_id: Optional[str] = None):
    """Knowledge base statistics — what the system has learned."""
    entries = knowledge_repo.list(project_id=project_id)
    auto    = [e for e in entries if "auto-extracted" in (e.get("tags") or [])]

    # Confidence distribution
    high_conf = []
    for e in auto:
        tags = e.get("tags", [])
        conf_tag = next((t for t in tags if t.startswith("confidence:")), None)
        if conf_tag:
            conf = float(conf_tag.split(":")[1])
            if conf >= 0.7:
                high_conf.append(e)

    by_category = {}
    for e in entries:
        cat = e.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total":           len(entries),
        "auto_extracted":  len(auto),
        "manual":          len(entries) - len(auto),
        "high_confidence": len(high_conf),
        "by_category":     by_category,
    }


@app.post("/api/v1/knowledge/search/semantic")
async def semantic_search(body: dict):
    """Semantic search over the knowledge base."""
    query      = body.get("query", "")
    engine     = body.get("engine", "normalizer")
    project_id = body.get("project_id")
    if not query:
        raise HTTPException(status_code=400, detail="query required")
    try:
        from utils.semantic_search import search_kb
        results = search_kb(query=query, engine=engine,
                            project_id=project_id, top_k=10)
        return {"query": query, "engine": engine, "results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Version Delta ─────────────────────────────────────────────────────────────
from utils.version_delta import compute_delta, propagate_impact

@app.get("/api/v1/stories/{story_id}/delta")
async def get_version_delta(story_id: str, v_from: int = None, v_to: int = None):
    """
    Compute delta between two versions of a story.
    Defaults to comparing latest vs previous.
    """
    from repositories.analysis import AnalysisRepository
    repo = AnalysisRepository()
    versions = repo.list_by_story_id(story_id)

    if len(versions) < 2:
        return {"has_changes": False, "summary": "Apenas uma versão disponível"}

    # Sort by version ascending
    versions_sorted = sorted(versions, key=lambda x: x.get("version", 0))

    if v_from is None or v_to is None:
        # Default: compare last two
        v_old = versions_sorted[-2]
        v_new = versions_sorted[-1]
    else:
        v_old = next((v for v in versions_sorted if v.get("version") == v_from), None)
        v_new = next((v for v in versions_sorted if v.get("version") == v_to),   None)

    if not v_old or not v_new:
        raise HTTPException(status_code=404, detail="Version not found")

    delta = compute_delta(
        old_text=v_old.get("requirement", ""),
        new_text=v_new.get("requirement", ""),
        story_id=story_id,
        v_from=v_old.get("version", 0),
        v_to=v_new.get("version", 0),
    )

    return delta.to_dict()


@app.get("/api/v1/stories/{story_id}/impact")
async def get_impact_analysis(story_id: str, v_from: int = None, v_to: int = None):
    """
    Full impact analysis: delta + propagation to affected tests/automations.
    """
    from repositories.analysis import AnalysisRepository
    repo = AnalysisRepository()
    versions = repo.list_by_story_id(story_id)

    if len(versions) < 2:
        return {"re_analysis_needed": False, "summary": "Apenas uma versão disponível"}

    versions_sorted = sorted(versions, key=lambda x: x.get("version", 0))
    v_old = versions_sorted[-2] if v_from is None else next((v for v in versions_sorted if v.get("version") == v_from), None)
    v_new = versions_sorted[-1] if v_to   is None else next((v for v in versions_sorted if v.get("version") == v_to),   None)

    if not v_old or not v_new:
        raise HTTPException(status_code=404, detail="Version not found")

    delta = compute_delta(
        old_text=v_old.get("requirement", ""),
        new_text=v_new.get("requirement", ""),
        story_id=story_id,
        v_from=v_old.get("version", 0),
        v_to=v_new.get("version", 0),
    )

    # Get traceability from latest analysis for propagation
    latest_full = analysis_repo.get(v_new.get("id", ""))
    tra_items = []
    if latest_full and latest_full.get("result"):
        tra = latest_full["result"].get("traceability", {})
        tra_items = tra.get("items", []) if tra else []

    impact = propagate_impact(delta, tra_items)
    impact["delta"] = delta.to_dict()

    return impact
