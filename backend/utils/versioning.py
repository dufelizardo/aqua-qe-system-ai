"""
utils/versioning.py
Versioning service for requirements.

Responsibilities:
- Detect if a requirement has been analyzed before (by story ID)
- Determine next version number
- Compare requirement text between versions (what changed)
- Provide version summary for the Hub
"""

from typing import Optional
from utils.id_detector import detect_story_id
from repositories.analysis import AnalysisRepository
from repositories.project  import ProjectRepository

analysis_repo = AnalysisRepository()
project_repo  = ProjectRepository()


class VersionInfo:
    """Result of a version check."""

    def __init__(self):
        self.story_id:       Optional[str] = None   # detected ID (e.g. BSAG-1724)
        self.is_new:         bool          = True    # True = first analysis
        self.current_version: int          = 0       # last version in DB
        self.next_version:    int          = 1       # what will be saved
        self.last_analysis:   Optional[dict] = None  # summary of last version
        self.text_changed:    bool          = False  # True if text differs from last version
        self.change_summary:  str          = ""      # what changed

    def to_dict(self) -> dict:
        return {
            "story_id":        self.story_id,
            "is_new":          self.is_new,
            "current_version": self.current_version,
            "next_version":    self.next_version,
            "text_changed":    self.text_changed,
            "change_summary":  self.change_summary,
            "last_analysis":   self.last_analysis,
        }


def check_version(requirement: str) -> VersionInfo:
    """
    Check if this requirement has been analyzed before.
    Uses story_id column directly — no text matching.
    """
    info = VersionInfo()

    # 1. Detect story ID from text
    story_id = detect_story_id(requirement)
    if not story_id:
        info.is_new = True
        info.next_version = 1
        return info

    info.story_id = story_id

    # 2. Look up by story_id column directly
    existing = analysis_repo.list_by_story_id(story_id)

    if not existing:
        info.is_new = True
        info.current_version = 0
        info.next_version = 1
        return info

    # 3. Story exists — get latest
    latest = existing[0]  # list_by_story_id returns newest first
    info.is_new = False
    info.current_version = latest.get("version", 1)
    info.next_version = info.current_version + 1
    info.last_analysis = {
        "id":            latest.get("id"),
        "version":       latest.get("version"),
        "overall_score": latest.get("overall_score"),
        "risk_level":    latest.get("risk_level"),
        "created_at":    str(latest.get("created_at", "")),
        "requirement":   latest.get("requirement", "")[:200],
    }

    # 4. Detect text changes
    last_req    = latest.get("requirement", "").strip()
    current_req = requirement.strip()

    if last_req != current_req:
        info.text_changed   = True
        info.change_summary = _summarize_changes(last_req, current_req)
    else:
        info.text_changed   = False
        info.change_summary = "Texto idêntico à versão anterior"

    return info


def get_story_versions(story_id: str) -> list[dict]:
    """
    Get all versions of a story, with comparison data.
    """
    existing = analysis_repo.list_recent(limit=100)
    story_analyses = [
        a for a in existing
        if _extract_id_from_req(a.get("requirement", "")) == story_id.upper()
    ]
    return sorted(story_analyses, key=lambda x: x.get("version", 1))


def _extract_id_from_req(req: str) -> Optional[str]:
    return detect_story_id(req)


def _summarize_changes(old: str, new: str) -> str:
    """Simple line-diff summary."""
    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())

    added   = [l for l in new_lines if l not in old_lines and l.strip()]
    removed = [l for l in old_lines if l not in new_lines and l.strip()]

    parts = []
    if added:
        parts.append(f"{len(added)} linha(s) adicionada(s)")
    if removed:
        parts.append(f"{len(removed)} linha(s) removida(s)")

    if not parts:
        return "Mudanças menores de formatação"

    return " · ".join(parts)
