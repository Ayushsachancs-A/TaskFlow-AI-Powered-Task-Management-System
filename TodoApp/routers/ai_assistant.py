"""
AI Assistant Router for Todo Application.
Provides RAG endpoints for natural language task queries, daily executive briefings, and duplicate detection.
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Todos
from .auth import get_current_user
from ..services import rag_service

router = APIRouter(
    prefix="/api/v1/ai",
    tags=["ai-assistant"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


# Request and Response Models
class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="Natural language query about user tasks")


class AskResponse(BaseModel):
    answer: str
    referenced_task_ids: List[int]
    tasks_found: List[dict]


class DuplicateCheckRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=500)
    priority: Optional[int] = Field(default=1, ge=1, le=5)


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    highest_similarity: float
    similar_tasks: List[dict]
    message: str


class BriefingResponse(BaseModel):
    summary: str
    metrics: dict
    high_priority_tasks: List[dict]
    action_items: List[str]


@router.post("/ask", response_model=AskResponse, status_code=status.HTTP_200_OK)
async def ask_task_assistant(
    user: user_dependency,
    request_data: AskRequest
):
    """
    RAG endpoint to query the user's isolated task vector store.
    Strictly filters by the authenticated user's ID.
    """
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed.")

    user_id = user.get("id")
    result = rag_service.ask_ai_assistant(query=request_data.query, user_id=user_id)
    return result


@router.get("/briefing", response_model=BriefingResponse, status_code=status.HTTP_200_OK)
async def get_daily_briefing(
    user: user_dependency,
    db: db_dependency
):
    """
    Synthesizes a prioritized morning executive briefing and action items
    based on the authenticated user's current tasks.
    """
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed.")

    user_id = user.get("id")
    todos = db.query(Todos).filter(Todos.owner_id == user_id).all()
    
    tasks_list = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "complete": t.complete,
            "owner_id": t.owner_id
        }
        for t in todos
    ]
    
    briefing = rag_service.generate_daily_briefing(user_id=user_id, active_tasks=tasks_list)
    return briefing


@router.post("/detect-duplicates", response_model=DuplicateCheckResponse, status_code=status.HTTP_200_OK)
async def check_duplicate_task(
    user: user_dependency,
    task_draft: DuplicateCheckRequest
):
    """
    Checks semantic cosine similarity against the user's active tasks in ChromaDB
    to alert user of potential duplicate or highly similar tasks.
    """
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed.")

    user_id = user.get("id")
    result = rag_service.detect_duplicates(
        title=task_draft.title,
        description=task_draft.description or "",
        priority=task_draft.priority or 1,
        user_id=user_id
    )
    return result
