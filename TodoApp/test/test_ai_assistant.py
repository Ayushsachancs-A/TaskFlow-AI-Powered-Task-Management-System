"""
Unit and integration tests for AI Assistant RAG endpoints and user isolation.
"""

import pytest
from fastapi import status
from .utils import client, TestingSessionLocal, engine, override_get_db, override_get_current_user, test_todo, test_user
from ..models import Todos, Users
from ..routers.ai_assistant import get_db, get_current_user
from ..main import app

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_ai_detect_duplicates(test_todo):
    """Test duplicate detection endpoint with high similarity."""
    payload = {
        "title": "Learn to code",
        "description": "Need to learn everyday",
        "priority": 5
    }
    response = client.post("/api/v1/ai/detect-duplicates", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "is_duplicate" in data
    assert "highest_similarity" in data
    assert "similar_tasks" in data


def test_ai_ask_endpoint(test_todo):
    """Test asking AI Copilot about user tasks."""
    payload = {
        "query": "What are my learning tasks?"
    }
    response = client.post("/api/v1/ai/ask", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "answer" in data
    assert "referenced_task_ids" in data
    assert "tasks_found" in data
    assert len(data["answer"]) > 0


def test_ai_briefing_endpoint(test_todo):
    """Test generating daily morning executive briefing."""
    response = client.get("/api/v1/ai/briefing")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "summary" in data
    assert "metrics" in data
    assert "high_priority_tasks" in data
    assert "action_items" in data
    assert data["metrics"]["total"] >= 1


def test_ai_user_isolation(test_todo):
    """Verify strict user isolation: User 2 cannot access User 1's tasks."""
    # Temporarily override user as User 2 (ID: 999)
    app.dependency_overrides[get_current_user] = lambda: {'username': 'OtherUser', 'id': 999, 'user_role': 'Member'}
    
    try:
        # User 2 asks about 'Learn to code'
        response = client.post("/api/v1/ai/ask", json={"query": "Learn to code"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # User 2 must NOT find User 1's task (ID: 1)
        assert 1 not in data["referenced_task_ids"]
        assert len(data["tasks_found"]) == 0
        
        # User 2's briefing should have 0 tasks
        briefing_resp = client.get("/api/v1/ai/briefing")
        assert briefing_resp.status_code == status.HTTP_200_OK
        briefing_data = briefing_resp.json()
        assert briefing_data["metrics"]["total"] == 0
    finally:
        # Restore default test user
        app.dependency_overrides[get_current_user] = override_get_current_user
