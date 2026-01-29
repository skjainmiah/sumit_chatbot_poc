"""Chat API endpoints - main orchestration point."""
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
from backend.pii.masker import mask_pii, unmask_pii
from backend.llm.client import get_llm_client
from backend.llm.prompts import GENERAL_CHAT_PROMPT
from backend.db.session import execute_write, execute_query
from backend.config import settings

logger = logging.getLogger("chatbot.api.chat")

router = APIRouter()


# Meta-query patterns (questions about database structure, not data)
META_QUERY_PATTERNS = [
    (r'\b(list|show|what|which)\b.*\b(database|databases|dbs)\b', 'databases'),
    (r'\b(list|show|what|which)\b.*\b(table|tables)\b', 'tables'),
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
    """Return predefined response for meta-queries about database structure."""

    if query_type == 'databases':
        response = """We have **4 operational databases** in the system:

**1. crew_management** - Crew member profiles, qualifications, assignments, rest records, documents, contacts, and roster data

**2. flight_operations** - Flights, aircraft, airports, crew pairings, flight legs, disruptions, and layover hotels

**3. hr_payroll** - Pay grades, payroll records, leave records/balances, benefits, performance reviews, and expense claims

**4. compliance_training** - Training courses, training records, schedules, enrollments, compliance checks, safety incidents, and audit logs

All databases are linked by **employee_id** (e.g., AA-10001) for cross-database queries.

You can ask questions like:
- "Show me all pilots"
- "What is John's salary?"
- "List expiring medical certificates"
- "Show flights to Dallas"
"""
        results = {
            "columns": ["database_name", "description", "table_count"],
            "rows": [
                {"database_name": "crew_management", "description": "Crew profiles, qualifications, assignments, roster", "table_count": 7},
                {"database_name": "flight_operations", "description": "Flights, aircraft, airports, pairings, hotels", "table_count": 8},
                {"database_name": "hr_payroll", "description": "Payroll, leave, benefits, performance, expenses", "table_count": 7},
                {"database_name": "compliance_training", "description": "Training, compliance checks, safety incidents", "table_count": 7},
            ],
            "row_count": 4
        }

    else:  # tables
        response = """Here are all **29 tables** across the 4 databases:

**crew_management (7 tables):**
- crew_members - Master crew records (name, role, base, status)
- crew_qualifications - Licenses, ratings, medical certificates
- crew_assignments - Flight assignments with duty times
- crew_rest_records - FAR 117 rest compliance tracking
- crew_documents - Passport, visa, license documents
- crew_contacts - Emergency contact information
- crew_roster - Monthly roster/bidding data

**flight_operations (8 tables):**
- flights - Flight schedule with times and status
- aircraft - Fleet information (type, capacity, status)
- airports - Airport codes, names, timezone, hub status
- crew_pairings - Duty trip groupings
- pairing_flights - Pairing-to-flight mappings
- flight_legs - Multi-segment flight legs
- disruptions - Delays, cancellations, diversions
- hotels - Crew layover hotels

**hr_payroll (7 tables):**
- pay_grades - Salary structure by role/seniority
- payroll_records - Monthly payroll data
- leave_records - Leave requests and approvals
- leave_balances - Leave entitlements by type
- benefits - Insurance, 401k enrollments
- performance_reviews - Annual performance ratings
- expense_claims - Expense reimbursements

**compliance_training (7 tables):**
- training_courses - Available training programs
- training_records - Completed training with scores
- training_schedules - Upcoming training sessions
- training_enrollments - Session enrollments
- compliance_checks - Regulatory compliance status
- safety_incidents - Safety incident reports
- audit_logs - System audit trail
"""
        results = {
            "columns": ["database", "table_name", "description"],
            "rows": [
                {"database": "crew_management", "table_name": "crew_members", "description": "Master crew records"},
                {"database": "crew_management", "table_name": "crew_qualifications", "description": "Licenses, ratings, certifications"},
                {"database": "crew_management", "table_name": "crew_assignments", "description": "Flight assignments"},
                {"database": "crew_management", "table_name": "crew_rest_records", "description": "FAR 117 rest tracking"},
                {"database": "crew_management", "table_name": "crew_documents", "description": "Passport, visa, licenses"},
                {"database": "crew_management", "table_name": "crew_contacts", "description": "Emergency contacts"},
                {"database": "crew_management", "table_name": "crew_roster", "description": "Monthly roster data"},
                {"database": "flight_operations", "table_name": "flights", "description": "Flight schedule"},
                {"database": "flight_operations", "table_name": "aircraft", "description": "Fleet information"},
                {"database": "flight_operations", "table_name": "airports", "description": "Airport master data"},
                {"database": "flight_operations", "table_name": "crew_pairings", "description": "Duty trip groupings"},
                {"database": "flight_operations", "table_name": "pairing_flights", "description": "Pairing-flight junction"},
                {"database": "flight_operations", "table_name": "flight_legs", "description": "Multi-segment legs"},
                {"database": "flight_operations", "table_name": "disruptions", "description": "Delays, cancellations"},
                {"database": "flight_operations", "table_name": "hotels", "description": "Layover hotels"},
                {"database": "hr_payroll", "table_name": "pay_grades", "description": "Salary structures"},
                {"database": "hr_payroll", "table_name": "payroll_records", "description": "Monthly payroll"},
                {"database": "hr_payroll", "table_name": "leave_records", "description": "Leave requests"},
                {"database": "hr_payroll", "table_name": "leave_balances", "description": "Leave entitlements"},
                {"database": "hr_payroll", "table_name": "benefits", "description": "Insurance, 401k"},
                {"database": "hr_payroll", "table_name": "performance_reviews", "description": "Performance ratings"},
                {"database": "hr_payroll", "table_name": "expense_claims", "description": "Expense reimbursements"},
                {"database": "compliance_training", "table_name": "training_courses", "description": "Training programs"},
                {"database": "compliance_training", "table_name": "training_records", "description": "Completed training"},
                {"database": "compliance_training", "table_name": "training_schedules", "description": "Training sessions"},
                {"database": "compliance_training", "table_name": "training_enrollments", "description": "Session enrollments"},
                {"database": "compliance_training", "table_name": "compliance_checks", "description": "Regulatory compliance"},
                {"database": "compliance_training", "table_name": "safety_incidents", "description": "Safety reports"},
                {"database": "compliance_training", "table_name": "audit_logs", "description": "Audit trail"},
            ],
            "row_count": 29
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

    # PII masking
    masked_query, pii_map = mask_pii(request.message)

    # Query rewriting for follow-ups
    processed_query = masked_query
    if history and needs_rewriting(masked_query):
        processed_query = rewrite_query(masked_query, history)

    # Intent classification
    intent_result = classify_intent(processed_query, history)

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

    # Check for meta-queries (about database structure) first
    is_meta, meta_type = check_meta_query(processed_query)

    if is_meta and meta_type:
        # Handle meta-queries directly without SQL generation
        response_text, sql_results = get_meta_response(meta_type)
        sql_query = f"-- Meta-query: {meta_type} (no SQL executed)"
        intent_result.intent = "DATA"  # Mark as DATA for UI display

    elif intent_result.intent == "DATA":
        # SQL Pipeline
        try:
            sql_pipeline = SQLPipeline()
            result = sql_pipeline.run(processed_query)

            if result["success"]:
                response_text = result["summary"]
                sql_query = result["sql"]
                sql_results = result["results"]
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

    # Unmask PII in response if needed
    if pii_map:
        response_text = unmask_pii(response_text, pii_map)

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
