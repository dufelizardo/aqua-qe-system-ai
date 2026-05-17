"""
repositories/knowledge.py
Corporate knowledge base CRUD.
"""

import uuid
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, delete, or_
from .base import BaseRepository
from models.database import knowledge, get_connection


class KnowledgeRepository(BaseRepository):

    def create(self, category: str, title: str, description: str,
               project_id: Optional[str] = None, context: Optional[str] = None,
               mitigation: Optional[str] = None, severity: Optional[str] = None,
               tags: Optional[List[str]] = None) -> dict:

        record = {
            "id":          str(uuid.uuid4()),
            "project_id":  project_id,
            "category":    category,
            "title":       title,
            "description": description,
            "context":     context,
            "mitigation":  mitigation,
            "severity":    severity,
            "tags":        json.dumps(tags or []),
            "created_at":  datetime.now(),
            "updated_at":  datetime.now(),
        }
        with get_connection() as conn:
            conn.execute(knowledge.insert().values(**record))
            conn.commit()
        record["tags"] = tags or []
        return record

    def get(self, knowledge_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(knowledge).where(knowledge.c.id == knowledge_id)
            ).mappings().first()
            return self._parse(dict(row)) if row else None

    def list(self, project_id: Optional[str] = None, category: Optional[str] = None) -> List[dict]:
        with get_connection() as conn:
            q = select(knowledge).order_by(knowledge.c.created_at.desc())
            if category:
                q = q.where(knowledge.c.category == category)
            if project_id:
                q = q.where(
                    or_(knowledge.c.project_id == project_id,
                        knowledge.c.project_id == None)
                )
            rows = conn.execute(q).mappings().all()
            return [self._parse(dict(r)) for r in rows]

    def search(self, query: str, project_id: Optional[str] = None) -> List[dict]:
        all_items = self.list(project_id=project_id)
        q = query.lower()
        return [
            item for item in all_items
            if q in item["title"].lower()
            or q in item["description"].lower()
            or any(q in tag.lower() for tag in item.get("tags", []))
        ]

    def get_context_for_analysis(self, keywords: List[str], project_id: Optional[str] = None) -> List[dict]:
        all_items = self.list(project_id=project_id)
        relevant = []
        for item in all_items:
            item_text = f"{item['title']} {item['description']} {' '.join(item.get('tags',[]))}".lower()
            score = sum(1 for kw in keywords if kw.lower() in item_text)
            if score > 0:
                relevant.append({**item, "_relevance": score})
        relevant.sort(key=lambda x: x["_relevance"], reverse=True)
        return relevant[:10]

    def update(self, knowledge_id: str, **fields) -> Optional[dict]:
        values = {"updated_at": datetime.now()}
        for f in ["title", "description", "context", "mitigation", "severity", "category"]:
            if f in fields:
                values[f] = fields[f]
        if "tags" in fields:
            values["tags"] = json.dumps(fields["tags"])
        with get_connection() as conn:
            conn.execute(update(knowledge).where(knowledge.c.id == knowledge_id).values(**values))
            conn.commit()
        return self.get(knowledge_id)

    def delete(self, knowledge_id: str):
        with get_connection() as conn:
            conn.execute(delete(knowledge).where(knowledge.c.id == knowledge_id))
            conn.commit()

    def _parse(self, row: dict) -> dict:
        if "tags" in row and isinstance(row["tags"], str):
            try:
                row["tags"] = json.loads(row["tags"])
            except Exception:
                row["tags"] = []
        return row
