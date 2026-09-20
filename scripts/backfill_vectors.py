#!/usr/bin/env python3
"""
One-time data migration script to backfill vector embeddings from SQLite into ChromaDB.
Scans all existing tasks in SQLite and indexes them into the user_task_store collection
with proper user_id tags for strict multi-tenant isolation.
"""

import sys
import os
from pathlib import Path

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from TodoApp.database import SessionLocal
from TodoApp.models import Todos, Users
from TodoApp.services import rag_service


def run_backfill():
    print("=" * 60)
    print("[*] Starting ChromaDB Vector Store Backfill Migration")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        users = db.query(Users).all()
        todos = db.query(Todos).all()
        
        print(f"[+] Found {len(users)} registered users and {len(todos)} total tasks in SQLite.")
        
        if not todos:
            print("[!] No tasks found in database to migrate.")
            return
            
        collection = rag_service.get_collection()
        
        synced_count = 0
        user_stats = {}
        
        for todo in todos:
            rag_service.upsert_task(
                task_id=todo.id,
                title=todo.title,
                description=todo.description,
                priority=todo.priority,
                complete=todo.complete,
                user_id=todo.owner_id
            )
            synced_count += 1
            user_stats[todo.owner_id] = user_stats.get(todo.owner_id, 0) + 1
            
        print("\n[+] Backfill completed successfully!")
        print(f"[+] Total vectors upserted: {synced_count}")
        print("[+] Tasks indexed per user:")
        for uid, count in user_stats.items():
            user = next((u for u in users if u.id == uid), None)
            uname = user.username if user else f"User #{uid}"
            print(f"   * {uname} (ID: {uid}): {count} tasks")
            
        print(f"[+] ChromaDB Collection count: {collection.count()} vectors stored in '{rag_service.CHROMA_PERSIST_DIR}'")
        print("=" * 60)
    except Exception as e:
        print(f"[X] Error during backfill migration: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_backfill()
