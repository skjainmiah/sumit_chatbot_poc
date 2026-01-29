"""Conversation memory and session management."""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from backend.db.session import get_app_db, execute_query, execute_write
from backend.config import settings


class ConversationManager:
    """Manages conversation sessions and message history."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.conversation_id: Optional[int] = None
        self.session_id: Optional[str] = None

    def create_conversation(self) -> int:
        """Create a new conversation session."""
        self.session_id = str(uuid.uuid4())
        self.conversation_id = execute_write(
            settings.app_db_path,
            """INSERT INTO conversations (user_id, session_id, started_at, last_message_at, message_count, is_active)
               VALUES (?, ?, ?, ?, 0, 1)""",
            (self.user_id, self.session_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
        )
        return self.conversation_id

    def get_or_create_conversation(self, conversation_id: Optional[int] = None) -> int:
        """Get existing conversation or create new one."""
        if conversation_id:
            # Verify conversation belongs to user
            convs = execute_query(
                settings.app_db_path,
                "SELECT conversation_id FROM conversations WHERE conversation_id = ? AND user_id = ? AND is_active = 1",
                (conversation_id, self.user_id)
            )
            if convs:
                self.conversation_id = conversation_id
                return conversation_id

        # Create new conversation
        return self.create_conversation()

    def add_message(
        self,
        role: str,
        content: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        sql_generated: Optional[str] = None,
        sql_result: Optional[dict] = None,
        source_documents: Optional[List[dict]] = None,
        pii_masked: bool = False,
        processing_time_ms: Optional[int] = None
    ) -> int:
        """Add a message to the conversation."""
        if not self.conversation_id:
            self.create_conversation()

        message_id = execute_write(
            settings.app_db_path,
            """INSERT INTO messages
               (conversation_id, role, content, intent, confidence, sql_generated,
                sql_result, source_documents, pii_masked, processing_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.conversation_id,
                role,
                content,
                intent,
                confidence,
                sql_generated,
                json.dumps(sql_result) if sql_result else None,
                json.dumps(source_documents) if source_documents else None,
                1 if pii_masked else 0,
                processing_time_ms
            )
        )

        # Update conversation
        execute_write(
            settings.app_db_path,
            """UPDATE conversations
               SET last_message_at = ?, message_count = message_count + 1
               WHERE conversation_id = ?""",
            (datetime.utcnow().isoformat(), self.conversation_id)
        )

        return message_id

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get conversation history."""
        if not self.conversation_id:
            return []

        messages = execute_query(
            settings.app_db_path,
            """SELECT role, content, intent, sql_generated, source_documents, created_at
               FROM messages
               WHERE conversation_id = ?
               ORDER BY message_id DESC
               LIMIT ?""",
            (self.conversation_id, limit)
        )

        # Reverse to get chronological order
        return list(reversed(messages))

    def get_recent_turns(self, n: int = 5) -> List[Dict[str, str]]:
        """Get last N turns for context."""
        history = self.get_history(limit=n * 2)  # Get more in case some are system
        turns = []
        for msg in history:
            if msg["role"] in ("user", "assistant"):
                turns.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        return turns[-n:] if len(turns) > n else turns

    def end_conversation(self):
        """Mark conversation as ended."""
        if self.conversation_id:
            execute_write(
                settings.app_db_path,
                "UPDATE conversations SET is_active = 0 WHERE conversation_id = ?",
                (self.conversation_id,)
            )


def get_user_conversations(user_id: int, limit: int = 20) -> List[Dict]:
    """Get user's conversation list."""
    return execute_query(
        settings.app_db_path,
        """SELECT conversation_id, session_id, started_at, last_message_at, message_count
           FROM conversations
           WHERE user_id = ? AND is_active = 1
           ORDER BY last_message_at DESC
           LIMIT ?""",
        (user_id, limit)
    )
