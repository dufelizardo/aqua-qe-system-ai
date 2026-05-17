"""
repositories/base.py
Abstract base repository.
All repositories inherit from this — consistent interface.
"""

from abc import ABC
from models.database import engine


class BaseRepository(ABC):
    """Base class for all repositories."""

    def __init__(self):
        self.engine = engine
