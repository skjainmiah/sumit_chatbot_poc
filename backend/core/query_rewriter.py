"""Query rewriter for follow-up questions."""
from typing import List, Dict
from backend.llm.client import get_llm_client
from backend.llm.prompts import QUERY_REWRITE_PROMPT


def rewrite_query(query: str, conversation_history: List[Dict[str, str]]) -> str:
    """Rewrite a follow-up query into a standalone question."""
    if not conversation_history:
        return query

    client = get_llm_client()

    # Format history
    history_str = ""
    for msg in conversation_history[-5:]:  # Last 5 turns
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_str += f"{role.capitalize()}: {content}\n"

    prompt = QUERY_REWRITE_PROMPT.format(
        history=history_str,
        query=query
    )

    response = client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=500
    )

    return response.strip()


def needs_rewriting(query: str) -> bool:
    """Check if a query likely needs rewriting (contains pronouns, references, or follow-up patterns)."""
    query_lower = f' {query.lower()} '

    # Pronouns that reference previous context
    pronouns = ['it', 'this', 'that', 'they', 'them', 'he', 'she', 'his', 'her', 'those', 'these']
    for word in pronouns:
        if f' {word} ' in query_lower:
            return True

    # Explicit references to previous conversation
    references = ['the same', 'above', 'previous', 'last', 'mentioned', 'earlier']
    for phrase in references:
        if f' {phrase} ' in query_lower:
            return True

    # Contradiction / follow-up starters — user is responding to a previous answer
    followup_starters = ['but ', 'however ', 'actually ', 'no ', 'wrong ', 'incorrect ',
                         'not right', 'that\'s not', 'thats not', 'wait ',
                         'what about ', 'how about ', 'and what ', 'and how ',
                         'also ', 'additionally ', 'what else', 'anything else',
                         'more about', 'tell me more', 'explain more',
                         'why not', 'why is', 'why are', 'why did',
                         'can you also', 'show me more', 'what if']
    stripped = query.strip().lower()
    for starter in followup_starters:
        if stripped.startswith(starter):
            return True

    # Short vague queries (< 5 words, no verb-like keywords) are likely follow-ups
    words = query.strip().split()
    if len(words) <= 3 and not any(kw in query_lower for kw in
            [' show ', ' list ', ' get ', ' find ', ' how many ', ' count ', ' what ']):
        return True

    return False
