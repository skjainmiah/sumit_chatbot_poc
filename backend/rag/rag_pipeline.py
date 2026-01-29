"""RAG pipeline for knowledge-based queries."""
import time
from typing import Dict, List, Optional
from backend.config import settings
from backend.llm.client import get_llm_client
from backend.llm.prompts import RAG_GENERATION_PROMPT
from backend.cache.vector_store import get_document_store


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for policy questions."""

    def __init__(self):
        self.llm_client = get_llm_client()

    def retrieve_documents(self, query: str, top_k: int = None) -> List[Dict]:
        """Retrieve relevant document chunks."""
        top_k = top_k or settings.RAG_TOP_K
        store = get_document_store()

        results = store.search(query, top_k=top_k)

        chunks = []
        for meta, score in results:
            chunks.append({
                "document_name": meta.get("document_name", "Unknown"),
                "document_title": meta.get("document_title", "Unknown"),
                "chunk_text": meta.get("chunk_text", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "relevance_score": score
            })

        return chunks

    def format_context(self, chunks: List[Dict]) -> str:
        """Format retrieved chunks for the prompt."""
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            formatted.append(f"""
[Source {i}: {chunk['document_title']}]
{chunk['chunk_text']}
""")
        return "\n---\n".join(formatted)

    def generate_answer(self, query: str, chunks: List[Dict]) -> str:
        """Generate answer from retrieved context."""
        context = self.format_context(chunks)

        prompt = RAG_GENERATION_PROMPT.format(
            context_chunks=context,
            query=query
        )

        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000
        )

        return response.strip()

    def run(self, query: str) -> Dict:
        """Run the full RAG pipeline."""
        start_time = time.time()

        # Step 1: Retrieve relevant documents
        chunks = self.retrieve_documents(query)

        if not chunks:
            return {
                "success": False,
                "answer": "I don't have any relevant policy documents to answer this question. Please make sure the policy documents have been ingested.",
                "sources": [],
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        # Step 2: Generate answer
        answer = self.generate_answer(query, chunks)

        # Format sources for response
        sources = [
            {
                "document": chunk["document_title"],
                "relevance": round(chunk["relevance_score"], 3)
            }
            for chunk in chunks
        ]

        return {
            "success": True,
            "answer": answer,
            "sources": sources,
            "chunks_used": len(chunks),
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }
