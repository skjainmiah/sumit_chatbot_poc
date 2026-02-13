"""
V2 chat endpoint - uses the full-schema pipeline for SQL generation.
Handles greetings, PII masking, and routes queries through the V2 pipeline.
"""

import time
import logging
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.auth.jwt_handler import verify_token
from backend.sql.pipeline_v2 import get_sql_pipeline
from backend.pii.masker import mask_pii, unmask_pii, get_pii_settings
from backend.llm.client import get_llm_client

logger = logging.getLogger("chatbot.api.chat_v2")
pii_logger = logging.getLogger("chatbot.pii.audit")


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[str] = None  # Previous conversation context


class ChatResponse(BaseModel):
    success: bool
    response: str
    intent: str  # meta, data, ambiguous, general, error
    conversation_id: Optional[str] = None
    sql_query: Optional[str] = None
    sql_results: Optional[dict] = None
    clarification: Optional[str] = None
    suggestions: Optional[List[str]] = None
    processing_time_ms: int
    error: Optional[str] = None


# Simple in-memory conversation store (replace with DB in production)
_conversations: dict = {}


def _get_conversation_context(conversation_id: str, limit: int = 5) -> str:
    """Get recent conversation context."""
    if not conversation_id or conversation_id not in _conversations:
        return ""

    messages = _conversations[conversation_id][-limit:]
    context_parts = []
    for msg in messages:
        role = msg["role"].capitalize()
        content = msg["content"][:200]  # Truncate for context
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


def _save_message(conversation_id: str, role: str, content: str):
    """Save message to conversation history."""
    if conversation_id:
        if conversation_id not in _conversations:
            _conversations[conversation_id] = []
        _conversations[conversation_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })


def _is_greeting(message: str) -> bool:
    """Check if message is a simple greeting."""
    greetings = {
        'hi', 'hello', 'hey', 'good morning', 'good afternoon',
        'good evening', 'thanks', 'thank you', 'bye', 'goodbye'
    }
    return message.strip().rstrip('!?.').lower() in greetings


def _get_greeting_response(message: str) -> str:
    """Get response for greetings."""
    msg_lower = message.strip().rstrip('!?.').lower()
    responses = {
        'hi': "Hello! I'm your database assistant. Ask me anything about your data - I can query across all databases.",
        'hello': "Hello! I'm your database assistant. Ask me anything about your data - I can query across all databases.",
        'hey': "Hey! How can I help you today? You can ask me about your databases, tables, or query any data.",
        'good morning': "Good morning! How can I assist you today?",
        'good afternoon': "Good afternoon! How can I assist you today?",
        'good evening': "Good evening! How can I assist you today?",
        'thanks': "You're welcome! Let me know if you need anything else.",
        'thank you': "You're welcome! Feel free to ask more questions.",
        'bye': "Goodbye! Have a great day!",
        'goodbye': "Goodbye! Have a great day!",
    }
    return responses.get(msg_lower, "Hello! How can I help you today?")


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, token: str = None):
    """Process a chat message and return response."""
    start_time = time.time()

    # Optional: Verify token (comment out for testing)
    if token:
        token_data = verify_token(token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid token")

    # Generate conversation ID if not provided
    conv_id = request.conversation_id or f"conv_{int(time.time() * 1000)}"

    # Save user message
    _save_message(conv_id, "user", request.message)

    # Handle simple greetings (no LLM needed)
    if _is_greeting(request.message):
        response_text = _get_greeting_response(request.message)
        _save_message(conv_id, "assistant", response_text)

        return ChatResponse(
            success=True,
            response=response_text,
            intent="general",
            conversation_id=conv_id,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )

    # PII masking with comprehensive logging
    pii_settings = get_pii_settings()
    pii_enabled = pii_settings.get('enabled', True)
    pii_log_enabled = pii_settings.get('log_enabled', True)

    if pii_log_enabled:
        pii_logger.info(f"[PII] === REQUEST START (conv={conv_id}) ===")
        pii_logger.info(f"[PII] PII masking enabled: {pii_enabled}")
        pii_logger.info(f"[PII] STEP 1 - User Input: \"{request.message}\"")

    masked_query, pii_map = mask_pii(request.message)

    if pii_log_enabled:
        if pii_map:
            pii_logger.info(f"[PII] STEP 2 - PII Detected: {len(pii_map)} item(s) masked")
            for token, original in pii_map.items():
                pii_logger.info(f"[PII]   {token} ← \"{original}\"")
            pii_logger.info(f"[PII] STEP 3 - Masked Input (sent to LLM): \"{masked_query}\"")
        else:
            pii_logger.info(f"[PII] STEP 2 - No PII detected in input")
            pii_logger.info(f"[PII] STEP 3 - Input to LLM (unchanged): \"{masked_query[:200]}\"")

    # Get conversation context
    context = request.context or _get_conversation_context(conv_id)

    # Run SQL pipeline
    try:
        logger.info(f"V2 request: conv={conv_id} query=\"{masked_query[:120]}\"")
        pipeline = get_sql_pipeline()
        result = pipeline.run(masked_query, context)
        logger.info(f"V2 result: success={result.get('success')} intent={result.get('intent')} "
                     f"time={result.get('processing_time_ms')}ms error={result.get('error')}")
    except Exception as e:
        elapsed = int((time.time() - start_time) * 1000)
        logger.error(f"V2 pipeline EXCEPTION for query '{masked_query}' after {elapsed}ms: "
                     f"{type(e).__name__}: {e}", exc_info=True)
        return ChatResponse(
            success=False,
            response="I'm having trouble processing your request right now. Could you try rephrasing your question?",
            intent="error",
            conversation_id=conv_id,
            error=str(e),
            processing_time_ms=elapsed
        )

    # Build response based on intent
    intent = result.get("intent", "data")

    if intent == "meta":
        response_text = result.get("answer", "")
    elif intent == "ambiguous":
        response_text = result.get("clarification", "Could you please provide more details?")
    elif result.get("success"):
        response_text = result.get("summary") or ""
        if not response_text.strip():
            response_text = "The query executed successfully but returned no data matching your criteria."
    else:
        logger.warning(f"V2 query failed: {result.get('error', 'unknown')}")
        response_text = ("I wasn't able to find an answer for that. "
                         "Could you try rephrasing your question or providing more details?")

    # Log LLM output and unmask PII in response
    if pii_log_enabled:
        pii_logger.info(f"[PII] STEP 4 - LLM Output (before unmask): \"{response_text[:500]}\"")

    if pii_map:
        response_text = unmask_pii(response_text, pii_map)
        if pii_log_enabled:
            pii_logger.info(f"[PII] STEP 5 - Final Response (after unmask): \"{response_text[:500]}\"")
            pii_logger.info(f"[PII] === REQUEST END (conv={conv_id}) ===")
    else:
        if pii_log_enabled:
            pii_logger.info(f"[PII] STEP 5 - Final Response (no PII to unmask): \"{response_text[:500]}\"")
            pii_logger.info(f"[PII] === REQUEST END (conv={conv_id}) ===")

    # Save assistant response
    _save_message(conv_id, "assistant", response_text)

    return ChatResponse(
        success=result.get("success", False) or intent in ("meta", "ambiguous"),
        response=response_text,
        intent=intent,
        conversation_id=conv_id,
        sql_query=result.get("sql"),
        sql_results=result.get("results"),
        clarification=result.get("clarification") if intent == "ambiguous" else None,
        suggestions=result.get("suggestions"),
        processing_time_ms=result.get("processing_time_ms", int((time.time() - start_time) * 1000)),
        error=result.get("error")
    )


@router.get("/schema/info")
async def get_schema_info(token: str = None):
    """Get information about available databases and tables."""
    from backend.schema.loader import get_schema_loader

    try:
        loader = get_schema_loader()
        stats = loader.get_stats()

        return {
            "success": True,
            "databases": loader.get_database_names(),
            "total_tables": stats.total_tables,
            "total_columns": stats.total_columns,
            "estimated_tokens": stats.estimated_tokens
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/schema/tables")
async def get_tables(database: str = None, token: str = None):
    """Get list of tables, optionally filtered by database."""
    from backend.schema.loader import get_schema_loader

    try:
        loader = get_schema_loader()
        tables = loader.get_table_names(database)

        return {
            "success": True,
            "database": database,
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/schema/reload")
async def reload_schema(token: str = None):
    """Reload schema from file (after re-extraction)."""
    from backend.schema.loader import reload_schema

    try:
        reload_schema()
        return {"success": True, "message": "Schema reloaded successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    checks = {
        "api": "ok",
        "database": "unknown",
        "schema": "unknown"
    }

    # Check database connection (SQLite multi-db)
    try:
        from backend.db.session import get_multi_db_connection
        conn = get_multi_db_connection()
        cursor = conn.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Check schema loaded
    try:
        from backend.schema.loader import get_schema_loader
        loader = get_schema_loader()
        stats = loader.get_stats()
        checks["schema"] = f"ok ({stats.total_tables} tables)"
    except Exception as e:
        checks["schema"] = f"error: {str(e)}"

    all_ok = all(v == "ok" or v.startswith("ok") for v in checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks
    }
