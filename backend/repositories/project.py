"""
repositories/project.py
Projects and User Stories CRUD.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, delete
from .base import BaseRepository
from models.database import projects, stories, get_connection


class ProjectRepository(BaseRepository):

    def create_project(self, name: str, description: Optional[str] = None) -> dict:
        project = {
            "id":          str(uuid.uuid4()),
            "name":        name,
            "description": description,
            "created_at":  datetime.now(),
            "updated_at":  datetime.now(),
        }
        with get_connection() as conn:
            conn.execute(projects.insert().values(**project))
            conn.commit()
        return project

    def get_project(self, project_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(projects).where(projects.c.id == project_id)
            ).mappings().first()
            return dict(row) if row else None

    def list_projects(self) -> List[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                select(projects).order_by(projects.c.name)
            ).mappings().all()
            return [dict(r) for r in rows]

    def update_project(self, project_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[dict]:
        values = {"updated_at": datetime.now()}
        if name:        values["name"]        = name
        if description: values["description"] = description
        with get_connection() as conn:
            conn.execute(update(projects).where(projects.c.id == project_id).values(**values))
            conn.commit()
        return self.get_project(project_id)

    def delete_project(self, project_id: str):
        with get_connection() as conn:
            conn.execute(delete(stories).where(stories.c.project_id == project_id))
            conn.execute(delete(projects).where(projects.c.id == project_id))
            conn.commit()

    def create_story(self, project_id: str, title: str, external_id: Optional[str] = None) -> dict:
        story = {
            "id":          str(uuid.uuid4()),
            "project_id":  project_id,
            "external_id": external_id,
            "title":       title,
            "created_at":  datetime.now(),
            "updated_at":  datetime.now(),
        }
        with get_connection() as conn:
            conn.execute(stories.insert().values(**story))
            conn.commit()
        return story

    def get_story(self, story_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(stories).where(stories.c.id == story_id)
            ).mappings().first()
            return dict(row) if row else None

    def get_story_by_external_id(self, project_id: str, external_id: str) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                select(stories).where(
                    stories.c.project_id  == project_id,
                    stories.c.external_id == external_id,
                )
            ).mappings().first()
            return dict(row) if row else None

    def list_stories(self, project_id: str) -> List[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                select(stories)
                .where(stories.c.project_id == project_id)
                .order_by(stories.c.created_at.desc())
            ).mappings().all()
            return [dict(r) for r in rows]

    def upsert_story(self, project_id: str, title: str, external_id: Optional[str] = None) -> dict:
        if external_id:
            existing = self.get_story_by_external_id(project_id, external_id)
            if existing:
                return existing
        return self.create_story(project_id, title, external_id)
