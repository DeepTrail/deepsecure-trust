"""Pydantic schemas for Task API list response."""

from typing import Any, Dict, List

from pydantic import BaseModel


class TaskListResponse(BaseModel):
    """Paginated list of tasks."""

    tasks: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int
