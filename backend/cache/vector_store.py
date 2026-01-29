"""FAISS-based vector store for embeddings."""
import os
import json
import pickle
import numpy as np
from typing import List, Dict, Tuple, Optional
from pathlib import Path

try:
    import faiss
except ImportError:
    faiss = None

from backend.config import settings
from backend.llm.embeddings import embed_query, embed_documents


class FAISSVectorStore:
    """FAISS-based vector store for similarity search."""

    def __init__(self, name: str, dimension: int = None):
        self.name = name
        self.dimension = dimension or settings.EMBEDDING_DIMENSIONS
        self.index: Optional['faiss.Index'] = None
        self.metadata: List[Dict] = []
        self.index_path = Path(settings.FAISS_INDEX_DIR) / f"{name}.index"
        self.metadata_path = Path(settings.FAISS_INDEX_DIR) / f"{name}.meta"

        # Ensure directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing index if available
        self.load()

    def load(self):
        """Load index from disk if exists."""
        if faiss is None:
            print("Warning: FAISS not installed, using numpy fallback")
            self.embeddings = []
            return

        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                print(f"Loaded FAISS index '{self.name}' with {len(self.metadata)} items")
            except Exception as e:
                print(f"Error loading index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        """Create a new FAISS index."""
        if faiss is None:
            self.embeddings = []
            return
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine with normalized vectors)
        self.metadata = []

    def save(self):
        """Save index to disk."""
        if faiss is None:
            return
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            print(f"Saved FAISS index '{self.name}' with {len(self.metadata)} items")

    def add(self, texts: List[str], metadata_list: List[Dict]):
        """Add texts with their metadata to the index."""
        if not texts:
            return

        # Generate embeddings
        embeddings = embed_documents(texts)

        # Normalize for cosine similarity
        embeddings_np = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_np)

        # Add to index
        self.index.add(embeddings_np)
        self.metadata.extend(metadata_list)

        # Save after adding
        self.save()

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search for similar items."""
        if faiss is None or self.index is None or self.index.ntotal == 0:
            return []

        # Generate query embedding
        query_embedding = np.array([embed_query(query)], dtype=np.float32)
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))

        # Return results with metadata
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.metadata):
                results.append((self.metadata[idx], float(score)))

        return results

    def clear(self):
        """Clear the index."""
        self._create_new_index()
        # Remove files
        if self.index_path.exists():
            self.index_path.unlink()
        if self.metadata_path.exists():
            self.metadata_path.unlink()

    @property
    def count(self) -> int:
        """Get number of items in index."""
        if faiss is None:
            return len(self.embeddings) if hasattr(self, 'embeddings') else 0
        return self.index.ntotal if self.index else 0


# Singleton instances
_schema_store: Optional[FAISSVectorStore] = None
_document_store: Optional[FAISSVectorStore] = None


def get_schema_store() -> FAISSVectorStore:
    """Get the schema metadata vector store."""
    global _schema_store
    if _schema_store is None:
        _schema_store = FAISSVectorStore("schema_metadata")
    return _schema_store


def get_document_store() -> FAISSVectorStore:
    """Get the document chunks vector store."""
    global _document_store
    if _document_store is None:
        _document_store = FAISSVectorStore("document_chunks")
    return _document_store
