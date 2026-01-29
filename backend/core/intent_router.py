"""Intent classification for routing queries to appropriate pipeline."""
import re
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from backend.llm.client import get_llm_client
from backend.llm.prompts import INTENT_CLASSIFICATION_PROMPT
from backend.config import settings


class IntentResult(BaseModel):
    intent: str  # DATA, GENERAL
    confidence: float
    reasoning: str
    follow_up_question: Optional[str] = None
    detected_entities: List[str] = []


# Fast pattern matching to skip LLM call for obvious intents
GENERAL_PATTERNS = re.compile(
    r'^(hi|hello|hey|good\s*(morning|afternoon|evening)|thanks|thank\s*you|bye|goodbye|ok|okay|sure|yes|no|help)[\s!?.]*$',
    re.IGNORECASE
)

# Data patterns: queries asking for specific records/data
DATA_PATTERNS = re.compile(
    r'(show\s*(me|all)?|list|how\s*many|count|total|get|display|fetch|find|lookup|search)\s*.*(crew|flight|pay|salary|leave|training|airport|aircraft|schedule|record|assignment|pairing|hotel|disruption|expense|benefit|compliance|incident)',
    re.IGNORECASE
)

DATA_KEYWORDS = re.compile(
    r'\b(database|databases|tables|schema|columns|rows|records|data available|policy|policies|procedure|procedures|guideline|guidelines|rule|rules|regulation|requirement|crew|flight|training|payroll|compliance)\b',
    re.IGNORECASE
)


def classify_intent(
    query: str,
    conversation_history: List[Dict[str, str]] = None
) -> IntentResult:
    """Classify the user's query intent."""

    # Fast path: greetings and simple messages → skip LLM
    if GENERAL_PATTERNS.match(query.strip()):
        return IntentResult(
            intent="GENERAL",
            confidence=0.99,
            reasoning="Pattern match: greeting/simple message",
            detected_entities=[]
        )

    # Fast path: obvious data queries → skip LLM
    if DATA_PATTERNS.search(query) or DATA_KEYWORDS.search(query):
        return IntentResult(
            intent="DATA",
            confidence=0.95,
            reasoning="Pattern match: data/database query",
            detected_entities=[]
        )

    # LLM classification for ambiguous queries - use fast model (gpt-4o-mini)
    client = get_llm_client()

    # Format conversation history
    history_str = ""
    if conversation_history:
        for msg in conversation_history[-3:]:  # Last 3 turns
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_str += f"{role.capitalize()}: {content}\n"
    else:
        history_str = "No previous conversation."

    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        conversation_history=history_str,
        query=query
    )

    response = client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        json_mode=True,
        use_fast_model=True,
        max_tokens=300
    )

    try:
        result = json.loads(response)
        intent = result.get("intent", "GENERAL").upper()
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "")
        follow_up = result.get("follow_up_question")
        entities = result.get("detected_entities", [])

        # If confidence is below threshold, set follow-up question
        if confidence < settings.INTENT_CONFIDENCE_THRESHOLD and not follow_up:
            follow_up = generate_clarification_question(query, intent)

        return IntentResult(
            intent=intent,
            confidence=confidence,
            reasoning=reasoning,
            follow_up_question=follow_up if confidence < settings.INTENT_CONFIDENCE_THRESHOLD else None,
            detected_entities=entities
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        # Default to GENERAL if parsing fails
        return IntentResult(
            intent="GENERAL",
            confidence=0.5,
            reasoning="Failed to parse intent classification response",
            follow_up_question=None,
            detected_entities=[]
        )


def generate_clarification_question(query: str, detected_intent: str) -> str:
    """Generate a clarification question when confidence is low."""
    if detected_intent == "DATA":
        return "I want to make sure I understand correctly. Are you asking me to look up specific records or data from our databases? For example, crew assignments, flight schedules, payroll, training, or compliance information?"
    else:
        return "Could you please clarify what you'd like help with? I can look up data like flight schedules, crew records, training information, payroll, and more from our databases."
