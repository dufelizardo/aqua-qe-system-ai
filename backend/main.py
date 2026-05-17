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
