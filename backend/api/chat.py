"""V1 chat endpoint - handles intent classification, PII masking, SQL pipeline, and general chat."""
import re
import time
import logging
from typing import Optional, List, Tuple
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.auth.jwt_handler import verify_token
from backend.core.intent_router import classify_intent
from backend.core.query_rewriter import rewrite_query, needs_rewriting
from backend.core.conversation_manager import ConversationManager, get_user_conversations
from backend.sql.sql_pipeline import SQLPipeline
from backend.pii.masker import mask_pii, unmask_pii, get_pii_settings
from backend.pii.pipeline_logger import log_pii_trace
from backend.pii.column_masker import get_column_mask_settings
from backend.llm.client import get_llm_client
from backend.llm.prompts import GENERAL_CHAT_PROMPT
from backend.db.session import execute_write, execute_query, get_multi_db_connection
from backend.db.registry import get_database_registry
from backend.config import settings

logger = logging.getLogger("chatbot.api.chat")
pii_logger = logging.getLogger("chatbot.pii.audit")

router = APIRouter()


# Meta-query patterns (questions about database structure, not data)
META_QUERY_PATTERNS = [
    # Database questions
    (r'\b(list|show|what|which|get|display)\b.*\b(database|databases|dbs|db)\b', 'databases'),
    (r'\b(how many|count|number of)\b.*\b(database|databases|dbs|db)\b', 'databases'),
    (r'\bdatabases?\s*(available|exist|do (we|you) have)', 'databases'),
    (r'\bavailable\b.*\bdatabases?\b', 'databases'),
    # Table questions
    (r'\b(list|show|what|which|get|display)\b.*\b(table|tables)\b', 'tables'),
    (r'\b(how many|count|number of)\b.*\b(table|tables)\b', 'tables'),
    (r'\b(what|which)\b.*\b(schema|schemas)\b', 'tables'),
    (r'\bdescribe\b.*\b(database|databases|table|tables)\b', 'tables'),
    (r'\b(database|db)\s*(structure|schema|info|information)\b', 'tables'),
]


def check_meta_query(query: str) -> Tuple[bool, Optional[str]]:
    """Check if query is asking about database structure (meta-query)."""
    query_lower = query.lower()
    for pattern, query_type in META_QUERY_PATTERNS:
        if re.search(pattern, query_lower):
            return True, query_type
    return False, None


def get_meta_response(query_type: str) -> Tuple[str, dict]:
    """Return a dynamic response for meta-queries about database structure.

    Reads from the database registry + actual table lists so the answer
    stays correct as databases are uploaded or hidden.
    """
    try:
        registry = get_database_registry()
        all_dbs = registry.get_all_databases()
        visible = {n: d for n, d in all_dbs.items() if d.get("is_visible") and n != "app"}
    except Exception:
        visible = {}

    # ---- databases ----
    if query_type == "databases":
        rows = []
        parts = []
        for idx, (name, info) in enumerate(visible.items(), 1):
            display = info.get("display_name") or name
            desc = info.get("description") or ""
            tcount = info.get("table_count") or 0
            rows.append({"database_name": name, "description": desc, "table_count": tcount})
            parts.append(f"**{idx}. {name}** - {desc}")

        response = (
            f"We have **{len(visible)} operational databases** in the system:\n\n"
            + "\n\n".join(parts)
            + "\n\nAll crew-related databases are linked by **employee_id** for cross-database queries."
        )
        results = {
            "columns": ["database_name", "description", "table_count"],
            "rows": rows,
            "row_count": len(rows),
        }

    # ---- tables ----
    else:
        table_rows = []
        response_parts = []
        total_tables = 0

        conn = get_multi_db_connection(visible_only=True)
        try:
            for db_name in visible:
                try:
                    cursor = conn.execute(
                        f"SELECT name FROM [{db_name}].sqlite_master WHERE type='table' ORDER BY name"
                    )
                    tables = [r["name"] for r in cursor.fetchall()]
                except Exception:
                    tables = []

                total_tables += len(tables)
                table_list = "\n".join(f"- {t}" for t in tables)
                response_parts.append(f"**{db_name} ({len(tables)} tables):**\n{table_list}")

                for t in tables:
                    table_rows.append({"database": db_name, "table_name": t})
        finally:
            conn.close()

        response = (
            f"Here are all **{total_tables} tables** across {len(visible)} databases:\n\n"
            + "\n\n".join(response_parts)
        )
        results = {
            "columns": ["database", "table_name"],
            "rows": table_rows,
            "row_count": total_tables,
        }

    return response, results


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    conversation_id: int
    message_id: int
    sql_query: Optional[str] = None
    sql_results: Optional[dict] = None
    sources: Optional[List[dict]] = None
    suggestions: Optional[List[str]] = None
    follow_up_question: Optional[str] = None
    processing_time_ms: int


class FeedbackRequest(BaseModel):
    message_id: int
    rating: str  # thumbs_up or thumbs_down
    comment: Optional[str] = None


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, token: str):
    """Process a chat message and return response."""
    start_time = time.time()

    # Verify token
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Initialize conversation
    conv_manager = ConversationManager(token_data.user_id)
    conv_id = conv_manager.get_or_create_conversation(request.conversation_id)

    # Get conversation history
    history = conv_manager.get_recent_turns(5)

    logger.info(f"V1 request: conv={conv_id} query=\"{request.message[:120]}\"")

    # PII masking with audit logging
    pii_settings = get_pii_settings()
    pii_log_enabled = pii_settings.get('log_enabled', True)

    if pii_log_enabled:
        pii_logger.info(f"[PII] === V1 REQUEST START (conv={conv_id}) ===")
        pii_logger.info(f"[PII] PII masking enabled: {pii_settings.get('enabled', True)}")
        pii_logger.info(f"[PII] STEP 1 - User Input: \"{request.message}\"")

    masked_query, pii_map = mask_pii(request.message)
    if pii_map:
        logger.info(f"V1 PII masked: {len(pii_map)} items")
        if pii_log_enabled:
            pii_logger.info(f"[PII] STEP 2 - PII Detected: {len(pii_map)} item(s) masked")
            for token, original in pii_map.items():
                pii_logger.info(f"[PII]   {token} ← \"{original}\"")
            pii_logger.info(f"[PII] STEP 3 - Masked Input (sent to LLM): \"{masked_query}\"")
    elif pii_log_enabled:
        pii_logger.info(f"[PII] STEP 2 - No PII detected in input")
        pii_logger.info(f"[PII] STEP 3 - Input to LLM (unchanged): \"{masked_query[:200]}\"")

    # Query rewriting for follow-ups
    processed_query = masked_query
    if history and needs_rewriting(masked_query):
        processed_query = rewrite_query(masked_query, history)
        logger.info(f"V1 rewritten query: \"{processed_query[:120]}\"")

    # Intent classification
    intent_result = classify_intent(processed_query, history)
    logger.info(f"V1 intent: {intent_result.intent} confidence={intent_result.confidence}")

    # Save user message
    user_msg_id = conv_manager.add_message(
        role="user",
        content=request.message,
        pii_masked=len(pii_map) > 0
    )

    # Check if we need clarification
    if intent_result.follow_up_question:
        # Save clarification request
        assistant_msg_id = conv_manager.add_message(
            role="assistant",
            content=intent_result.follow_up_question,
            intent="CLARIFICATION",
            confidence=intent_result.confidence,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )

        return ChatResponse(
            response=intent_result.follow_up_question,
            intent="CLARIFICATION",
            confidence=intent_result.confidence,
            conversation_id=conv_id,
            message_id=assistant_msg_id,
            follow_up_question=intent_result.follow_up_question,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )

    # Route to appropriate pipeline
    response_text = ""
    sql_query = None
    sql_results = None
    sources = None
    suggestions = None

    # Check for meta-queries (about database structure) first
    is_meta, meta_type = check_meta_query(processed_query)

    if is_meta and meta_type:
        # Handle meta-queries directly without SQL generation
        response_text, sql_results = get_meta_response(meta_type)
        sql_query = f"-- Meta-query: {meta_type} (no SQL executed)"
        intent_result.intent = "DATA"  # Mark as DATA for UI display

    elif intent_result.intent == "DATA":
        # SQL Pipeline — build concise conversation context for follow-up handling
        # Only include user questions fully; keep assistant responses very brief
        # to avoid SQL column names / data values misleading the SQL generator
        conversation_context = ""
        if history:
            context_parts = []
            for msg in history[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    context_parts.append(f"User: {content[:150]}")
                else:
                    # Truncate assistant responses aggressively — the LLM only
                    # needs to know WHAT was answered, not the full data
                    context_parts.append(f"Assistant: {content[:80]}")
            conversation_context = "\n".join(context_parts)

        try:
            sql_pipeline = SQLPipeline()
            result = sql_pipeline.run(processed_query, context=conversation_context)

            if result["success"]:
                response_text = result.get("summary") or ""
                if not response_text.strip():
                    response_text = "The query executed successfully but returned no data matching your criteria."
                sql_query = result["sql"]
                sql_results = result["results"]
                suggestions = result.get("suggestions")
            else:
                logger.warning(f"V1 SQL pipeline failed: {result.get('error', 'unknown')}")
                response_text = ("I wasn't able to find an answer for that. "
                                 "Could you try rephrasing your question or providing more details?")
        except Exception as e:
            logger.error(f"V1 pipeline error for query '{processed_query}': {e}", exc_info=True)
            response_text = ("I'm having trouble processing your request right now. "
                             "Could you try rephrasing your question?")

    else:  # GENERAL
        # Quick response for simple greetings (skip LLM call)
        simple_greetings = {
            'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening',
            'thanks', 'thank you', 'bye', 'goodbye'
        }
        query_lower = processed_query.strip().rstrip('!?.').lower()

        if query_lower in simple_greetings:
            greetings_map = {
                'hi': "Hello! I'm your American Airlines Crew Assistant. I can help you with crew policies, flight data, training records, and more. What would you like to know?",
                'hello': "Hello! I'm your American Airlines Crew Assistant. I can help you with crew policies, flight data, training records, and more. What would you like to know?",
                'hey': "Hey there! I'm your American Airlines Crew Assistant. How can I help you today?",
                'good morning': "Good morning! How can I assist you today?",
                'good afternoon': "Good afternoon! How can I assist you today?",
                'good evening': "Good evening! How can I assist you today?",
                'thanks': "You're welcome! Let me know if you need anything else.",
                'thank you': "You're welcome! Feel free to ask if you have more questions.",
                'bye': "Goodbye! Have a great day!",
                'goodbye': "Goodbye! Have a great day!",
            }
            response_text = greetings_map.get(query_lower, "Hello! How can I help you today?")
        else:
            # General chat via LLM (use fast model)
            client = get_llm_client()
            history_str = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history[-3:]])

            prompt = GENERAL_CHAT_PROMPT.format(
                history=history_str if history_str else "No previous conversation.",
                query=processed_query
            )

            response_text = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
                use_fast_model=True
            )

    # Log LLM output and unmask PII in response
    if pii_log_enabled:
        pii_logger.info(f"[PII] STEP 4 - LLM Output (before unmask): \"{response_text[:500]}\"")

    if pii_map:
        response_text = unmask_pii(response_text, pii_map)
        if pii_log_enabled:
            pii_logger.info(f"[PII] STEP 5 - Final Response (after unmask): \"{response_text[:500]}\"")
            pii_logger.info(f"[PII] === V1 REQUEST END (conv={conv_id}) ===")
    elif pii_log_enabled:
        pii_logger.info(f"[PII] STEP 5 - Final Response (no PII to unmask): \"{response_text[:500]}\"")
        pii_logger.info(f"[PII] === V1 REQUEST END (conv={conv_id}) ===")

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"V1 response: intent={intent_result.intent} has_sql={sql_query is not None} "
                f"has_results={sql_results is not None} suggestions={len(suggestions) if suggestions else 0} "
                f"time={elapsed_ms}ms")

    # Log full PII pipeline trace (dedicated log file)
    if intent_result.intent == "DATA" and sql_query and not sql_query.startswith("-- Meta"):
        try:
            log_pii_trace(
                conv_id=str(conv_id),
                pii_settings=pii_settings,
                column_mask_settings=get_column_mask_settings(),
                user_prompt=request.message,
                masked_prompt=masked_query,
                pii_map=pii_map,
                sql=sql_query,
                results=sql_results,
                masked_results=result.get("masked_results"),
                summary=response_text,
            )
        except Exception:
            logger.debug("PII pipeline trace logging failed", exc_info=True)

    # Save assistant response
    assistant_msg_id = conv_manager.add_message(
        role="assistant",
        content=response_text,
        intent=intent_result.intent,
        confidence=intent_result.confidence,
        sql_generated=sql_query,
        sql_result=sql_results,
        source_documents=sources,
        pii_masked=len(pii_map) > 0,
        processing_time_ms=int((time.time() - start_time) * 1000)
    )

    return ChatResponse(
        response=response_text,
        intent=intent_result.intent,
        confidence=intent_result.confidence,
        conversation_id=conv_id,
        message_id=assistant_msg_id,
        sql_query=sql_query,
        sql_results=sql_results,
        sources=sources,
        suggestions=suggestions,
        processing_time_ms=int((time.time() - start_time) * 1000)
    )


@router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: int, token: str, limit: int = 50):
    """Get conversation history."""
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Verify conversation belongs to user
    convs = execute_query(
        settings.app_db_path,
        "SELECT conversation_id FROM conversations WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, token_data.user_id)
    )
    if not convs:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = execute_query(
        settings.app_db_path,
        """SELECT message_id, role, content, intent, confidence, sql_generated,
                  source_documents, processing_time_ms, created_at
           FROM messages WHERE conversation_id = ?
           ORDER BY message_id LIMIT ?""",
        (conversation_id, limit)
    )

    return {"conversation_id": conversation_id, "messages": messages}


@router.get("/conversations")
async def list_conversations(token: str, limit: int = 20):
    """List user's conversations."""
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    conversations = get_user_conversations(token_data.user_id, limit)
    return {"conversations": conversations}


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest, token: str):
    """Submit feedback for a message."""
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    if request.rating not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(status_code=400, detail="Rating must be thumbs_up or thumbs_down")

    execute_write(
        settings.app_db_path,
        "INSERT INTO feedback (message_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
        (request.message_id, token_data.user_id, request.rating, request.comment)
    )

    return {"status": "success", "message": "Feedback submitted"}


@router.post("/new")
async def new_conversation(token: str):
    """Start a new conversation."""
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    conv_manager = ConversationManager(token_data.user_id)
    conv_id = conv_manager.create_conversation()

    return {"conversation_id": conv_id}
