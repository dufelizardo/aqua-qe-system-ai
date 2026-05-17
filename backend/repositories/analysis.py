"""
repositories/analysis.py
Save and retrieve pipeline analysis results with versioning.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func, delete
from .base import BaseRepository
from models.database import analyses, get_connection, to_json, from_json


class AnalysisRepository(BaseRepository):

    def save(self, result, requirement: str, context: Optional[str] = None,
             story_id: Optional[str] = None, project_id: Optional[str] = None,
             provider: Optional[str] = None, model: Optional[str] = None) -> dict:

        version = self._next_version(story_id) if story_id else 1

        synth    = result.synthesis
        amb      = result.ambiguity
        risk     = result.risk
        rules    = result.rules
        gap      = result.gap
        coverage = result.coverage

        record = {
            "id":             result.request_id or str(uuid.uuid4()),
            "story_id":       story_id,
            "project_id":     project_id,
            "requirement":    requirement,
            "context":        context,
            "status":         result.status.value if result.status else "done",
            "version":        version,
            "provider":       provider,
            "model":          model,
            "overall_score":  synth.overall_score    if synth    else None,
            "ambiguity_score":amb.score               if amb      else None,
            "risk_score":     risk.score              if risk     else None,
            "rules_score":    rules.score             if rules    else None,
            "gap_score":      gap.score               if gap      else None,
            "coverage_score": coverage.score          if coverage else None,
            "risk_level":     risk.risk_level         if risk     else None,
            "result_json":    to_json(result),
            "total_time":     result.timings.total    if result.timings else None,
            "error":          result.error,
            "created_at":     datetime.now(),
        }

        with get_connection() as conn:
            conn.execute(analyses.insert().values(**record))
            conn.commit()

        return record

    def get(self, analysis_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(analyses).where(analyses.c.id == analysis_id)
            ).mappings().first()
            if not row:
                return None
            r = dict(row)
            r["result"] = from_json(r.pop("result_json", None))
            return r

    def list_by_story(self, story_id: str) -> List[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                select(
                    analyses.c.id, analyses.c.version, analyses.c.status,
                    analyses.c.overall_score, analyses.c.ambiguity_score,
                    analyses.c.risk_score, analyses.c.gap_score,
                    analyses.c.coverage_score, analyses.c.risk_level,
                    analyses.c.total_time, analyses.c.error,
                    analyses.c.created_at, analyses.c.requirement,
                )
                .where(analyses.c.story_id == story_id)
                .order_by(analyses.c.version.desc())
            ).mappings().all()
            return [dict(r) for r in rows]

    def list_by_story_id(self, story_id: str) -> List[dict]:
        """
        All analyses for a story_id, newest first.
        Uses story_id column directly — correct for versioning.
        """
        with get_connection() as conn:
            rows = conn.execute(
                select(
                    analyses.c.id, analyses.c.version, analyses.c.status,
                    analyses.c.overall_score, analyses.c.risk_level,
                    analyses.c.total_time, analyses.c.created_at,
                    analyses.c.requirement, analyses.c.error,
                )
                .where(analyses.c.story_id == story_id.upper())
                .order_by(analyses.c.version.desc())
            ).mappings().all()
            return [dict(r) for r in rows]

    def list_recent(self, project_id: Optional[str] = None, limit: int = 20) -> List[dict]:
        with get_connection() as conn:
            q = select(
                analyses.c.id, analyses.c.story_id, analyses.c.project_id,
                analyses.c.version, analyses.c.status, analyses.c.overall_score,
                analyses.c.risk_level, analyses.c.total_time, analyses.c.created_at,
                analyses.c.requirement, analyses.c.error,
            ).order_by(analyses.c.created_at.desc()).limit(limit)

            if project_id:
                q = q.where(analyses.c.project_id == project_id)

            rows = conn.execute(q).mappings().all()
            return [dict(r) for r in rows]

    def get_latest_by_story(self, story_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(analyses)
                .where(analyses.c.story_id == story_id)
                .order_by(analyses.c.version.desc())
                .limit(1)
            ).mappings().first()
            if not row:
                return None
            r = dict(row)
            r["result"] = from_json(r.pop("result_json", None))
            return r

    def compare_versions(self, story_id: str, v1: int, v2: int) -> dict:
        with get_connection() as conn:
            rows = conn.execute(
                select(analyses)
                .where(
                    analyses.c.story_id == story_id,
                    analyses.c.version.in_([v1, v2])
                )
            ).mappings().all()

        versions = {r["version"]: dict(r) for r in rows}
        a = versions.get(v1)
        b = versions.get(v2)

        if not a or not b:
            return {"error": "Version not found"}

        def delta(field):
            va, vb = a.get(field), b.get(field)
            return (vb - va) if va is not None and vb is not None else None

        return {
            "story_id": story_id,
            "v1": v1, "v2": v2,
            "v1_date": str(a["created_at"]),
            "v2_date": str(b["created_at"]),
            "deltas": {
                "overall_score":   delta("overall_score"),
                "ambiguity_score": delta("ambiguity_score"),
                "risk_score":      delta("risk_score"),
                "gap_score":       delta("gap_score"),
                "coverage_score":  delta("coverage_score"),
            },
            "risk_level_changed": a.get("risk_level") != b.get("risk_level"),
            "v1_risk_level": a.get("risk_level"),
            "v2_risk_level": b.get("risk_level"),
        }

    def delete_story_analyses(self, story_id: str):
        with get_connection() as conn:
            conn.execute(delete(analyses).where(analyses.c.story_id == story_id))
            conn.commit()

    def _next_version(self, story_id: str) -> int:
        with get_connection() as conn:
            result = conn.execute(
                select(func.max(analyses.c.version))
                .where(analyses.c.story_id == story_id)
            ).scalar()
            return (result or 0) + 1
