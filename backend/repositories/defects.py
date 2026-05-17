"""
repositories/defects.py
Manages defects (bugs) linked to specific stories and versions.

Supports:
- Jira ID reference (BSAG-089)
- Type: qa | production | regression
- Status lifecycle: open → fixed → reopened → wont_fix
- Linked to story version when found/fixed
- Inherited by child stories (improvements)
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, delete, or_
from .base import BaseRepository
from models.database import defects, get_connection


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

TYPE_LABEL = {
    "qa":          "QA",
    "production":  "Produção",
    "regression":  "Regressão",
}

STATUS_LABEL = {
    "open":      "Aberto",
    "fixed":     "Corrigido",
    "reopened":  "Reaberto",
    "wont_fix":  "Não será corrigido",
}


class DefectsRepository(BaseRepository):

    def create(self,
               story_id: str,
               title: str,
               severity: str,
               defect_type: str,
               jira_id: Optional[str] = None,
               description: Optional[str] = None,
               story_version: Optional[int] = None,
               sprint_found: Optional[str] = None,
               sprint_fixed: Optional[str] = None,
               fixed_in_version: Optional[int] = None,
               evidence: Optional[str] = None,
               status: str = "open") -> dict:

        record = {
            "id":               str(uuid.uuid4()),
            "jira_id":          jira_id.upper().strip() if jira_id else None,
            "story_id":         story_id.upper().strip(),
            "story_version":    story_version,
            "title":            title,
            "description":      description,
            "severity":         severity,
            "defect_type":      defect_type,
            "status":           status,
            "sprint_found":     sprint_found,
            "sprint_fixed":     sprint_fixed,
            "fixed_in_version": fixed_in_version,
            "evidence":         evidence,
            "created_at":       datetime.now(),
            "updated_at":       datetime.now(),
        }
        with get_connection() as conn:
            conn.execute(defects.insert().values(**record))
            conn.commit()
        return record

    def get(self, defect_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(defects).where(defects.c.id == defect_id)
            ).mappings().first()
            return dict(row) if row else None

    def get_by_jira_id(self, jira_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(defects).where(defects.c.jira_id == jira_id.upper())
            ).mappings().first()
            return dict(row) if row else None

    def list_by_story(self, story_id: str,
                      include_inherited: bool = False) -> List[dict]:
        """
        Get all defects for a story.
        If include_inherited=True, also returns defects from child stories.
        """
        story_id = story_id.upper()
        with get_connection() as conn:
            rows = conn.execute(
                select(defects)
                .where(defects.c.story_id == story_id)
                .order_by(defects.c.created_at.desc())
            ).mappings().all()
            result = [dict(r) for r in rows]

        # Sort by severity
        result.sort(key=lambda x: SEVERITY_ORDER.get(x.get("severity", "low"), 99))
        return result

    def list_open(self, story_id: Optional[str] = None) -> List[dict]:
        """Get all open or reopened defects, optional story filter."""
        with get_connection() as conn:
            q = select(defects).where(
                defects.c.status.in_(["open", "reopened"])
            ).order_by(defects.c.created_at.desc())
            if story_id:
                q = q.where(defects.c.story_id == story_id.upper())
            rows = conn.execute(q).mappings().all()
            return [dict(r) for r in rows]

    def update_status(self, defect_id: str, status: str,
                      sprint_fixed: Optional[str] = None,
                      fixed_in_version: Optional[int] = None) -> Optional[dict]:
        values = {"status": status, "updated_at": datetime.now()}
        if sprint_fixed:     values["sprint_fixed"]     = sprint_fixed
        if fixed_in_version: values["fixed_in_version"] = fixed_in_version
        with get_connection() as conn:
            conn.execute(update(defects).where(defects.c.id == defect_id).values(**values))
            conn.commit()
        return self.get(defect_id)

    def update(self, defect_id: str, **fields) -> Optional[dict]:
        allowed = [
            "title", "description", "severity", "defect_type",
            "status", "sprint_found", "sprint_fixed",
            "fixed_in_version", "evidence", "jira_id"
        ]
        values = {"updated_at": datetime.now()}
        for f in allowed:
            if f in fields:
                values[f] = fields[f]
        with get_connection() as conn:
            conn.execute(update(defects).where(defects.c.id == defect_id).values(**values))
            conn.commit()
        return self.get(defect_id)

    def delete(self, defect_id: str):
        with get_connection() as conn:
            conn.execute(delete(defects).where(defects.c.id == defect_id))
            conn.commit()

    def get_summary(self, story_id: str) -> dict:
        """
        Summary of defects for a story — used by pipeline context.
        """
        all_defects = self.list_by_story(story_id)
        return {
            "story_id":  story_id,
            "total":     len(all_defects),
            "open":      len([d for d in all_defects if d["status"] in ("open","reopened")]),
            "fixed":     len([d for d in all_defects if d["status"] == "fixed"]),
            "critical":  len([d for d in all_defects if d["severity"] == "critical"]),
            "high":      len([d for d in all_defects if d["severity"] == "high"]),
            "by_type": {
                "qa":         len([d for d in all_defects if d["defect_type"] == "qa"]),
                "production": len([d for d in all_defects if d["defect_type"] == "production"]),
                "regression": len([d for d in all_defects if d["defect_type"] == "regression"]),
            },
            "defects": all_defects[:5],  # top 5 by severity for context
        }

    def format_for_pipeline(self, story_id: str) -> str:
        """
        Format defects as context string for the Normalizer pipeline.
        Returns empty string if no defects.
        """
        summary = self.get_summary(story_id)
        if summary["total"] == 0:
            return ""

        lines = [f"\nDEFEITOS HISTÓRICOS DA HISTÓRIA {story_id}:"]
        lines.append(
            f"Total: {summary['total']} "
            f"({summary['open']} abertos, {summary['fixed']} corrigidos)"
        )

        for d in summary["defects"]:
            status_lbl = STATUS_LABEL.get(d["status"], d["status"])
            type_lbl   = TYPE_LABEL.get(d["defect_type"], d["defect_type"])
            jira       = f" · {d['jira_id']}" if d.get("jira_id") else ""
            ver        = f" · encontrado na v{d['story_version']}" if d.get("story_version") else ""
            fixed_ver  = f" · corrigido na v{d['fixed_in_version']}" if d.get("fixed_in_version") else ""

            lines.append(
                f"\n[{d['severity'].upper()} · {type_lbl} · {status_lbl}{jira}{ver}{fixed_ver}]"
                f" {d['title']}"
            )
            if d.get("description"):
                lines.append(f"  → {d['description'][:200]}")

        return "\n".join(lines)
