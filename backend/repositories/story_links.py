"""
repositories/story_links.py
Manages two types of relationships:

1. Story → Story (parent/child)
   - BSAG-1724 (principal) → BSAG-1891 (melhoria)
   - link_type: improvement | bugfix | dependency | related

2. Knowledge → Story
   - Bug BUG-089 vinculado à BSAG-1724
   - Integração API-ISIN vinculada à BSAG-1724
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, delete, or_
from .base import BaseRepository
from models.database import story_links, knowledge_story, knowledge, get_connection


LINK_TYPE_LABEL = {
    "improvement": "Melhoria",
    "bugfix":      "Correção de Bug",
    "dependency":  "Dependência",
    "related":     "Relacionada",
}


class StoryLinksRepository(BaseRepository):

    # ── Story → Story ─────────────────────────────────────────────────────────

    def link_stories(self, parent_id: str, child_id: str,
                     link_type: str = "improvement",
                     description: Optional[str] = None) -> dict:
        """Link a child story to a parent story."""
        parent_id = parent_id.upper().strip()
        child_id  = child_id.upper().strip()

        # Check if already linked
        existing = self._get_story_link(parent_id, child_id)
        if existing:
            return existing

        record = {
            "id":          str(uuid.uuid4()),
            "parent_id":   parent_id,
            "child_id":    child_id,
            "link_type":   link_type,
            "description": description,
            "created_at":  datetime.now(),
        }
        with get_connection() as conn:
            conn.execute(story_links.insert().values(**record))
            conn.commit()
        return record

    def get_children(self, parent_id: str) -> List[dict]:
        """Get all stories linked as children of a parent story."""
        with get_connection() as conn:
            rows = conn.execute(
                select(story_links)
                .where(story_links.c.parent_id == parent_id.upper())
                .order_by(story_links.c.created_at)
            ).mappings().all()
            return [dict(r) for r in rows]

    def get_parent(self, child_id: str) -> Optional[dict]:
        """Get the parent story of a child story."""
        with get_connection() as conn:
            row = conn.execute(
                select(story_links)
                .where(story_links.c.child_id == child_id.upper())
                .limit(1)
            ).mappings().first()
            return dict(row) if row else None

    def get_family(self, story_id: str) -> dict:
        """
        Get full family tree for a story:
        - its parent (if it's a child)
        - its children (if it's a parent)
        - siblings (other children of the same parent)
        """
        story_id = story_id.upper()
        parent   = self.get_parent(story_id)
        children = self.get_children(story_id)

        siblings = []
        if parent:
            siblings = [
                c for c in self.get_children(parent["parent_id"])
                if c["child_id"] != story_id
            ]

        return {
            "story_id": story_id,
            "parent":   parent,
            "children": children,
            "siblings": siblings,
            "is_improvement": parent is not None,
            "has_improvements": len(children) > 0,
        }

    def unlink_stories(self, parent_id: str, child_id: str):
        with get_connection() as conn:
            conn.execute(
                delete(story_links)
                .where(
                    story_links.c.parent_id == parent_id.upper(),
                    story_links.c.child_id  == child_id.upper(),
                )
            )
            conn.commit()

    # ── Knowledge → Story ─────────────────────────────────────────────────────

    def link_knowledge_to_story(self, knowledge_id: str, story_id: str,
                                note: Optional[str] = None) -> dict:
        """Link a knowledge entry to a specific story ID."""
        story_id = story_id.upper().strip()

        # Check duplicate
        existing = self._get_knowledge_link(knowledge_id, story_id)
        if existing:
            return existing

        record = {
            "id":           str(uuid.uuid4()),
            "knowledge_id": knowledge_id,
            "story_id":     story_id,
            "note":         note,
            "linked_at":    datetime.now(),
        }
        with get_connection() as conn:
            conn.execute(knowledge_story.insert().values(**record))
            conn.commit()
        return record

    def get_knowledge_for_story(self, story_id: str) -> List[dict]:
        """
        Get all knowledge entries linked to a story.
        Returns full knowledge entry data with link metadata.
        """
        import json
        story_id = story_id.upper()
        with get_connection() as conn:
            rows = conn.execute(
                select(
                    knowledge_story.c.id.label("link_id"),
                    knowledge_story.c.note,
                    knowledge_story.c.linked_at,
                    knowledge.c.id.label("knowledge_id"),
                    knowledge.c.category,
                    knowledge.c.title,
                    knowledge.c.description,
                    knowledge.c.context,
                    knowledge.c.mitigation,
                    knowledge.c.severity,
                    knowledge.c.tags,
                )
                .join(knowledge, knowledge.c.id == knowledge_story.c.knowledge_id)
                .where(knowledge_story.c.story_id == story_id)
                .order_by(knowledge_story.c.linked_at.desc())
            ).mappings().all()

            result = []
            for r in rows:
                d = dict(r)
                if isinstance(d.get("tags"), str):
                    try:    d["tags"] = json.loads(d["tags"])
                    except: d["tags"] = []
                result.append(d)
            return result

    def unlink_knowledge_from_story(self, knowledge_id: str, story_id: str):
        with get_connection() as conn:
            conn.execute(
                delete(knowledge_story)
                .where(
                    knowledge_story.c.knowledge_id == knowledge_id,
                    knowledge_story.c.story_id     == story_id.upper(),
                )
            )
            conn.commit()

    def get_story_context(self, story_id: str) -> dict:
        """
        Full context for a story — used by the pipeline to enrich analysis.
        Includes: direct knowledge links + inherited from parent story.
        """
        story_id = story_id.upper()
        direct   = self.get_knowledge_for_story(story_id)

        # If this is a child story, also get parent's knowledge
        parent_knowledge = []
        parent = self.get_parent(story_id)
        if parent:
            parent_knowledge = self.get_knowledge_for_story(parent["parent_id"])

        return {
            "story_id":         story_id,
            "direct_knowledge": direct,
            "inherited_knowledge": parent_knowledge,
            "parent_story":     parent,
            "total_entries":    len(direct) + len(parent_knowledge),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_story_link(self, parent_id: str, child_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(story_links)
                .where(
                    story_links.c.parent_id == parent_id,
                    story_links.c.child_id  == child_id,
                )
            ).mappings().first()
            return dict(row) if row else None

    def _get_knowledge_link(self, knowledge_id: str, story_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(knowledge_story)
                .where(
                    knowledge_story.c.knowledge_id == knowledge_id,
                    knowledge_story.c.story_id     == story_id,
                )
            ).mappings().first()
            return dict(row) if row else None
