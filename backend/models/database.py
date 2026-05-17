"""
models/database.py
SQLite connection and table definitions.
Uses SQLAlchemy Core (no ORM) — simple, fast, no magic.
"""

from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    String, Integer, Float, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone
from utils.config import settings
import json

# ── Engine ───────────────────────────────────────────────────────────────────
engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

metadata = MetaData()

# ── Tables ───────────────────────────────────────────────────────────────────

# Projects — top level container (ex: PetFriends, BSAG)
projects = Table("projects", metadata,
    Column("id",          String(36),  primary_key=True),
    Column("name",        String(200), nullable=False),
    Column("description", Text,        nullable=True),
    Column("created_at",  DateTime,    default=datetime.now),
    Column("updated_at",  DateTime,    default=datetime.now, onupdate=datetime.now),
)

# User Stories / Requirements — belong to a project
stories = Table("stories", metadata,
    Column("id",          String(36),  primary_key=True),
    Column("project_id",  String(36),  ForeignKey("projects.id"), nullable=False),
    Column("external_id", String(100), nullable=True),   # ex: US-001, BSAG-1724
    Column("title",       String(500), nullable=False),
    Column("created_at",  DateTime,    default=datetime.now),
    Column("updated_at",  DateTime,    default=datetime.now),
    Index("ix_stories_project", "project_id"),
    Index("ix_stories_external", "external_id"),
)

# Analyses — each run of the pipeline for a story
analyses = Table("analyses", metadata,
    Column("id",           String(36),  primary_key=True),
    Column("story_id",     String(36),  ForeignKey("stories.id"), nullable=True),
    Column("project_id",   String(36),  nullable=True),
    Column("requirement",  Text,        nullable=False),
    Column("context",      Text,        nullable=True),
    Column("status",       String(20),  nullable=False, default="done"),
    Column("version",      Integer,     nullable=False, default=1),
    Column("provider",     String(50),  nullable=True),
    Column("model",        String(100), nullable=True),

    # Engine scores (quick access without parsing JSON)
    Column("overall_score",   Integer, nullable=True),
    Column("ambiguity_score", Integer, nullable=True),
    Column("risk_score",      Integer, nullable=True),
    Column("rules_score",     Integer, nullable=True),
    Column("gap_score",       Integer, nullable=True),
    Column("coverage_score",  Integer, nullable=True),
    Column("risk_level",      String(20), nullable=True),

    # Full result stored as JSON
    Column("result_json",  Text,        nullable=True),

    Column("total_time",   Float,       nullable=True),
    Column("error",        Text,        nullable=True),
    Column("created_at",   DateTime,    default=datetime.now),

    Index("ix_analyses_story",   "story_id"),
    Index("ix_analyses_project", "project_id"),
    Index("ix_analyses_created", "created_at"),
)

# Knowledge base entries
knowledge = Table("knowledge", metadata,
    Column("id",          String(36),  primary_key=True),
    Column("project_id",  String(36),  nullable=True),   # None = global
    Column("category",    String(50),  nullable=False),  # padrao|bug|integ|gloss|comp|risco|heur
    Column("title",       String(500), nullable=False),
    Column("description", Text,        nullable=False),
    Column("context",     Text,        nullable=True),
    Column("mitigation",  Text,        nullable=True),
    Column("severity",    String(20),  nullable=True),
    Column("tags",        Text,        nullable=True),   # JSON array
    Column("created_at",  DateTime,    default=datetime.now),
    Column("updated_at",  DateTime,    default=datetime.now),
    Index("ix_knowledge_project",  "project_id"),
    Index("ix_knowledge_category", "category"),
)

# Knowledge entries linked to specific story IDs
knowledge_story = Table("knowledge_story", metadata,
    Column("id",           String(36), primary_key=True),
    Column("knowledge_id", String(36), ForeignKey("knowledge.id"), nullable=False),
    Column("story_id",     String(100), nullable=False),  # e.g. BSAG-1724
    Column("note",         Text,        nullable=True),   # why this entry is linked
    Column("linked_at",    DateTime,    default=datetime.now),
    Index("ix_ks_story",     "story_id"),
    Index("ix_ks_knowledge", "knowledge_id"),
)

# Story relationships — improvements linked to parent story
story_links = Table("story_links", metadata,
    Column("id",          String(36),  primary_key=True),
    Column("parent_id",   String(100), nullable=False),  # e.g. BSAG-1724 (história principal)
    Column("child_id",    String(100), nullable=False),  # e.g. BSAG-1891 (melhoria)
    Column("link_type",   String(50),  nullable=False, default="improvement"),
    # link_type: improvement | bugfix | dependency | related
    Column("description", Text,        nullable=True),
    Column("created_at",  DateTime,    default=datetime.now),
    Index("ix_sl_parent", "parent_id"),
    Index("ix_sl_child",  "child_id"),
)

# Defects — bugs linked to specific stories and versions
defects = Table("defects", metadata,
    Column("id",               String(36),  primary_key=True),
    Column("jira_id",          String(100), nullable=True),   # BSAG-089
    Column("story_id",         String(100), nullable=False),  # BSAG-1724
    Column("story_version",    Integer,     nullable=True),   # version when found
    Column("title",            String(500), nullable=False),
    Column("description",      Text,        nullable=True),
    Column("severity",         String(20),  nullable=False),  # critical|high|medium|low
    Column("defect_type",      String(20),  nullable=False),  # qa|production|regression
    Column("status",           String(20),  nullable=False,  default="open"),
    # status: open | fixed | reopened | wont_fix
    Column("sprint_found",     String(100), nullable=True),
    Column("sprint_fixed",     String(100), nullable=True),
    Column("fixed_in_version", Integer,     nullable=True),
    Column("evidence",         Text,        nullable=True),
    Column("created_at",       DateTime,    default=datetime.now),
    Column("updated_at",       DateTime,    default=datetime.now),
    Index("ix_defects_story",  "story_id"),
    Index("ix_defects_jira",   "jira_id"),
    Index("ix_defects_status", "status"),
)


# ── Init ─────────────────────────────────────────────────────────────────────
def init_db():
    """Create all tables if they don't exist."""
    metadata.create_all(engine)


def get_connection():
    """Context manager for database connections."""
    return engine.connect()


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_json(obj) -> str:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(mode='json'), default=str)
    return json.dumps(obj, default=str)


def from_json(s: str):
    if not s:
        return None
    return json.loads(s)
