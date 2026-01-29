"""Embedding utilities."""
from typing import List
from backend.llm.client import get_llm_client


def embed_query(text: str) -> List[float]:
    """Generate embedding for a query text."""
    client = get_llm_client()
    return client.generate_embedding(text)


def embed_documents(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple documents."""
    client = get_llm_client()
    return client.generate_embeddings_batch(texts)
