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
    """Check if a query likely needs rewriting (contains pronouns or references)."""
    pronouns = ['it', 'this', 'that', 'they', 'them', 'he', 'she', 'his', 'her', 'those', 'these']
    references = ['the same', 'above', 'previous', 'last', 'mentioned', 'earlier']

    query_lower = query.lower()
    for word in pronouns + references:
        if f' {word} ' in f' {query_lower} ':
            return True
    return False
