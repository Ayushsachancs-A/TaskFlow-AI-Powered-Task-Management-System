"""
Vector Store & RAG Service for Todo Application.
Provides user-isolated vector storage using ChromaDB and LLM-assisted task intelligence.
"""

import os
import math
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("rag_service")
logger.setLevel(logging.INFO)

# Global clients cached lazily
_chroma_client = None
_collection = None
_embedding_function = None

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "user_task_store"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


class LocalFallbackEmbeddingFunction:
    """
    Resilient, lightweight local embedding generator.
    Produces normalized deterministic dense vectors when OpenAI or ONNX embeddings are not available.
    """
    def supported_spaces(self) -> List[str]:
        return ["cosine", "l2", "ip"]

    def is_legacy(self) -> bool:
        return False

    def get_config(self) -> dict:
        return {"dim": self.dim}

    def __init__(self, dim: int = 128):
        self.dim = dim

    @staticmethod
    def name() -> str:
        return "LocalFallbackEmbeddingFunction"

    def __call__(self, input: Any) -> List[List[float]]:
        embeddings = []
        if isinstance(input, str):
            input = [input]
        for item in input:
            if isinstance(item, list):
                text = " ".join(str(t) for t in item)
            elif not isinstance(item, str):
                text = str(item) if item is not None else ""
            else:
                text = item
            vec = [0.0] * self.dim
            words = text.lower().split()
            if not words:
                embeddings.append(vec)
                continue
            for i, word in enumerate(words):
                for j, char in enumerate(word):
                    idx = (ord(char) * 31 + j * 7 + i) % self.dim
                    vec[idx] += 1.0
            # Normalize vector to unit length for accurate cosine similarity
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        return self(documents)

    def embed_query(self, input: Any) -> List[List[float]]:
        return self(input)


def get_embedding_function():
    """Initializes and returns the appropriate embedding function."""
    global _embedding_function
    if _embedding_function is not None:
        return _embedding_function

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    
    # Only use OpenAI's proprietary text-embedding-3-small if using a genuine OpenAI key without custom base_url (Groq/Ollama do not host text-embedding-3-small)
    if api_key.startswith("sk-") and not base_url:
        try:
            import chromadb.utils.embedding_functions as ef
            _embedding_function = ef.OpenAIEmbeddingFunction(
                api_key=api_key,
                model_name="text-embedding-3-small"
            )
            logger.info("Using OpenAI text-embedding-3-small for ChromaDB embeddings.")
            return _embedding_function
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAIEmbeddingFunction ({e}). Falling back.")

    _embedding_function = LocalFallbackEmbeddingFunction()
    return _embedding_function


def get_collection():
    """Initializes and returns the persistent ChromaDB collection."""
    global _chroma_client, _collection
    if _collection is not None:
        return _collection

    import chromadb
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    emb_fn = get_embedding_function()
    _collection = _chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"}
    )
    return _collection


def format_task_document(title: str, description: str, priority: int, complete: bool) -> str:
    """Standardized text representation of a task for vector chunking."""
    status_str = "Completed" if complete else "Pending"
    return f"Title: {title.strip()} | Description: {description.strip()} | Priority: {priority} | Status: {status_str}"


def upsert_task(task_id: int, title: str, description: str, priority: int, complete: bool, user_id: int) -> None:
    """
    Inserts or updates a task vector embedding in ChromaDB with strict user metadata.
    """
    try:
        coll = get_collection()
        doc_text = format_task_document(title, description, priority, complete)
        status_str = "Completed" if complete else "Pending"
        
        metadata = {
            "task_id": int(task_id),
            "user_id": int(user_id),
            "status": status_str,
            "priority": int(priority),
            "title": str(title)
        }
        
        coll.upsert(
            ids=[f"task_{task_id}"],
            documents=[doc_text],
            metadatas=[metadata]
        )
        logger.info(f"Upserted vector for task_id={task_id}, user_id={user_id}")
    except Exception as e:
        logger.error(f"Error upserting task {task_id} into ChromaDB: {e}")


def delete_task(task_id: int, user_id: int) -> None:
    """
    Deletes the vector for a given task ID.
    """
    try:
        coll = get_collection()
        coll.delete(ids=[f"task_{task_id}"])
        logger.info(f"Deleted vector for task_id={task_id}, user_id={user_id}")
    except Exception as e:
        logger.error(f"Error deleting task {task_id} from ChromaDB: {e}")


def query_tasks(query: str, user_id: int, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    Strictly isolated user vector search.
    Only returns tasks belonging to the specified user_id.
    """
    try:
        coll = get_collection()
        results = coll.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": int(user_id)}
        )
        
        matched_tasks = []
        if results and "ids" in results and results["ids"]:
            ids = results["ids"][0]
            docs = results["documents"][0] if "documents" in results and results["documents"] else []
            metadatas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else []
            distances = results["distances"][0] if "distances" in results and results["distances"] else []
            
            for i in range(len(ids)):
                matched_tasks.append({
                    "id": ids[i],
                    "task_id": metadatas[i].get("task_id") if i < len(metadatas) else None,
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None
                })
        return matched_tasks
    except Exception as e:
        logger.error(f"Error querying ChromaDB for user {user_id}: {e}")
        return []


def detect_duplicates(title: str, description: str, priority: int, user_id: int, threshold: float = 0.78) -> Dict[str, Any]:
    """
    Checks cosine similarity against existing active user tasks.
    Returns whether a duplicate draft is suspected.
    """
    try:
        query_doc = format_task_document(title, description, priority, complete=False)
        coll = get_collection()
        
        # Query top 3 similar tasks for this user
        results = coll.query(
            query_texts=[query_doc],
            n_results=3,
            where={"user_id": int(user_id)}
        )
        
        similar_tasks = []
        max_similarity = 0.0
        
        if results and "ids" in results and results["ids"] and len(results["ids"][0]) > 0:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else []
            distances = results["distances"][0] if "distances" in results and results["distances"] else []
            docs = results["documents"][0] if "documents" in results and results["documents"] else []
            
            for i in range(len(ids)):
                dist = distances[i] if i < len(distances) else 1.0
                # Cosine distance in [0, 2]; similarity = max(0, 1 - distance)
                similarity = max(0.0, min(1.0, 1.0 - dist))
                if similarity > max_similarity:
                    max_similarity = similarity
                
                meta = metadatas[i] if i < len(metadatas) else {}
                similar_tasks.append({
                    "task_id": meta.get("task_id"),
                    "title": meta.get("title", ""),
                    "status": meta.get("status", "Pending"),
                    "priority": meta.get("priority", 1),
                    "similarity_score": round(similarity, 3),
                    "document": docs[i] if i < len(docs) else ""
                })
        
        is_dup = max_similarity >= threshold
        msg = ""
        if is_dup:
            top_match = similar_tasks[0]
            msg = f"⚠️ High similarity detected ({int(top_match['similarity_score'] * 100)}%) with existing task #{top_match['task_id']}: '{top_match['title']}'"
            
        return {
            "is_duplicate": is_dup,
            "highest_similarity": round(max_similarity, 3),
            "similar_tasks": similar_tasks,
            "message": msg
        }
    except Exception as e:
        logger.error(f"Error detecting duplicates for user {user_id}: {e}")
        return {
            "is_duplicate": False,
            "highest_similarity": 0.0,
            "similar_tasks": [],
            "message": ""
        }


def ask_ai_assistant(query: str, user_id: int, user_context_tasks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    RAG Assistant: Vector searches user tasks, constructs prompt, calls LLM, and formats response.
    """
    # 1. Retrieve user-isolated relevant tasks
    retrieved = query_tasks(query, user_id=user_id, n_results=5)
    
    context_chunks = []
    referenced_ids = []
    for item in retrieved:
        tid = item.get("task_id")
        doc = item.get("document", "")
        if tid:
            referenced_ids.append(tid)
            context_chunks.append(f"[Task #{tid}] {doc}")
        elif doc:
            context_chunks.append(doc)
            
    context_text = "\n".join(context_chunks) if context_chunks else "No specific matching tasks found in your task list."
    
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    
    # 2. Call LLM if API key or custom base_url is present
    if api_key or base_url:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)
            
            system_prompt = (
                "You are an intelligent, proactive AI Task Assistant and Executive Copilot for the user's Todo application. "
                "Your objective is to provide precise, actionable, and structured insights based strictly on the user's tasks provided in the context.\n\n"
                "Rules:\n"
                "1. Always reference specific tasks using the format: `[Task #<ID>: <Title>]`.\n"
                "2. Categorize responses clearly with Markdown headers, bold highlights, and bullet points.\n"
                "3. If the user asks for prioritization, emphasize high-priority and pending tasks.\n"
                "4. If no tasks match or context is empty, politely inform the user and suggest next steps.\n"
                "5. Never hallucinate tasks from other users."
            )
            
            user_prompt = f"User Query: {query}\n\nRetrieved Tasks Context:\n{context_text}"
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=600
            )
            
            answer = response.choices[0].message.content
            return {
                "answer": answer,
                "referenced_task_ids": referenced_ids,
                "tasks_found": retrieved
            }
        except Exception as e:
            logger.warning(f"LLM API call failed ({e}). Generating dynamic fallback answer.")

    # 3. Dynamic Fallback Generator (works offline without API keys)
    q_lower = query.lower()
    if not retrieved:
        answer = "### 📋 No Matching Tasks Found\n\nI couldn't find any tasks matching your query in your task list. Try adding new tasks or asking about pending/high priority items."
    else:
        answer_lines = [
            f"### 🤖 AI Task Assistant Response",
            f"Here is what I found regarding **\"{query}\"** based on your personal task records:\n"
        ]
        
        for item in retrieved:
            meta = item.get("metadata", {})
            tid = meta.get("task_id", item.get("task_id"))
            title = meta.get("title", "Untitled Task")
            status = meta.get("status", "Pending")
            priority = meta.get("priority", 1)
            p_badge = "🔴 High" if priority >= 4 else ("🟡 Medium" if priority == 3 else "🟢 Low")
            status_icon = "✅ Done" if status == "Completed" else "⏳ In Progress"
            
            answer_lines.append(f"- **[Task #{tid}: {title}]** — {status_icon} | Priority: {p_badge} (Level {priority})")
            if "Description:" in item.get("document", ""):
                desc = item["document"].split("Description:")[1].split("|")[0].strip()
                if desc:
                    answer_lines.append(f"  > _{desc}_")
                    
        answer_lines.append("\n**💡 Actionable Tip:** Focus on high priority incomplete tasks first to optimize your daily productivity!")
        answer = "\n".join(answer_lines)
        
    return {
        "answer": answer,
        "referenced_task_ids": referenced_ids,
        "tasks_found": retrieved
    }


def generate_daily_briefing(user_id: int, active_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates an executive morning briefing and prioritized action items.
    """
    total = len(active_tasks)
    pending = [t for t in active_tasks if not t.get("complete")]
    completed = [t for t in active_tasks if t.get("complete")]
    high_priority = [t for t in pending if t.get("priority", 1) >= 4]
    med_priority = [t for t in pending if t.get("priority", 1) == 3]
    low_priority = [t for t in pending if t.get("priority", 1) <= 2]
    
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    
    if api_key or base_url:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)
            
            tasks_formatted = "\n".join([
                f"- [Task #{t.get('id')}] {t.get('title')} | Priority: {t.get('priority')} | Status: {'Completed' if t.get('complete') else 'Pending'} | Details: {t.get('description')}"
                for t in active_tasks
            ])
            
            system_prompt = (
                "You are an elite productivity executive assistant. Formulate a crisp, motivating morning executive briefing for the user based on their task list.\n"
                "Include:\n"
                "1. **Executive Overview**: High-level workload summary and momentum score.\n"
                "2. **Top Priority Action Items**: The most urgent tasks to tackle first with task IDs `[Task #<ID>: <Title>]`.\n"
                "3. **Quick Wins & Secondary Tasks**: Lower friction tasks.\n"
                "4. **Strategic Focus of the Day**: A short motivating closing sentence."
            )
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User Task List:\n{tasks_formatted}"}
                ],
                temperature=0.3,
                max_tokens=650
            )
            
            summary = response.choices[0].message.content
            return {
                "summary": summary,
                "metrics": {
                    "total": total,
                    "pending": len(pending),
                    "completed": len(completed),
                    "high_priority": len(high_priority)
                },
                "high_priority_tasks": high_priority,
                "action_items": [f"[Task #{t.get('id')}] {t.get('title')}" for t in high_priority[:3]]
            }
        except Exception as e:
            logger.warning(f"OpenAI briefing call failed ({e}). Falling back to structured analytical briefing.")

    # Structured Analytical Briefing Fallback
    summary_parts = [
        "## 🌅 Daily Executive Morning Briefing",
        f"Good day! You have **{len(pending)} pending tasks** and **{len(completed)} completed tasks** on your radar today.",
        ""
    ]
    
    if high_priority:
        summary_parts.append("### 🚨 Urgent & High Priority Focus")
        for t in high_priority:
            summary_parts.append(f"- **[Task #{t.get('id')}: {t.get('title')}]** (Priority {t.get('priority')}/5) — {t.get('description')}")
        summary_parts.append("")
        
    if med_priority:
        summary_parts.append("### ⚡ Next in Line")
        for t in med_priority[:3]:
            summary_parts.append(f"- **[Task #{t.get('id')}: {t.get('title')}]** — {t.get('description')}")
        summary_parts.append("")
        
    if low_priority:
        summary_parts.append("### 🎯 Quick Wins")
        for t in low_priority[:2]:
            summary_parts.append(f"- **[Task #{t.get('id')}: {t.get('title')}]** — {t.get('description')}")
        summary_parts.append("")
        
    if not pending:
        summary_parts.append("🎉 **Incredible work!** All your tasks are completed. Take time to plan your upcoming goals or take a well-deserved break!")
    else:
        summary_parts.append("**💡 Productivity Recommendation:** Knock out your top high-priority task before noon to build unbeatable momentum.")

    return {
        "summary": "\n".join(summary_parts),
        "metrics": {
            "total": total,
            "pending": len(pending),
            "completed": len(completed),
            "high_priority": len(high_priority)
        },
        "high_priority_tasks": high_priority,
        "action_items": [f"[Task #{t.get('id')}] {t.get('title')}" for t in high_priority[:3]]
    }
