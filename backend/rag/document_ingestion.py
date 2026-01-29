"""Document ingestion for RAG - loads and chunks policy documents."""
import os
import re
from pathlib import Path
from typing import List, Dict
from backend.config import settings
from backend.cache.vector_store import get_document_store


class DocumentIngestion:
    """Ingests markdown documents into the vector store."""

    def __init__(self):
        self.chunk_size = settings.RAG_CHUNK_SIZE
        self.chunk_overlap = settings.RAG_CHUNK_OVERLAP

    def load_documents(self, directory: str = None) -> List[Dict]:
        """Load all markdown documents from directory."""
        directory = directory or settings.POLICY_DOCS_DIR
        docs_path = Path(directory)

        if not docs_path.exists():
            print(f"Documents directory not found: {directory}")
            return []

        documents = []
        for file_path in sorted(docs_path.glob("*.md")):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract title from first line
            lines = content.strip().split('\n')
            title = lines[0].replace('#', '').strip() if lines else file_path.stem

            documents.append({
                "name": file_path.name,
                "title": title,
                "content": content,
                "path": str(file_path)
            })

        return documents

    def chunk_document(self, document: Dict) -> List[Dict]:
        """Split document into chunks."""
        content = document["content"]
        chunks = []

        # Split by paragraphs first, then by size
        paragraphs = re.split(r'\n\n+', content)

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append({
                        "document_name": document["name"],
                        "document_title": document["title"],
                        "chunk_index": chunk_index,
                        "chunk_text": current_chunk.strip()
                    })
                    chunk_index += 1

                # Start new chunk with overlap
                if len(para) > self.chunk_size:
                    # Split large paragraph
                    words = para.split()
                    current_chunk = ""
                    for word in words:
                        if len(current_chunk) + len(word) <= self.chunk_size:
                            current_chunk += word + " "
                        else:
                            if current_chunk.strip():
                                chunks.append({
                                    "document_name": document["name"],
                                    "document_title": document["title"],
                                    "chunk_index": chunk_index,
                                    "chunk_text": current_chunk.strip()
                                })
                                chunk_index += 1
                            current_chunk = word + " "
                else:
                    current_chunk = para + "\n\n"

        # Add last chunk
        if current_chunk.strip():
            chunks.append({
                "document_name": document["name"],
                "document_title": document["title"],
                "chunk_index": chunk_index,
                "chunk_text": current_chunk.strip()
            })

        return chunks

    def ingest_all(self, directory: str = None):
        """Ingest all documents into vector store."""
        documents = self.load_documents(directory)

        if not documents:
            print("No documents found to ingest")
            return

        store = get_document_store()
        store.clear()

        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)
            print(f"  {doc['name']}: {len(chunks)} chunks")

        # Prepare for indexing
        texts = [c["chunk_text"] for c in all_chunks]
        metadata = all_chunks

        store.add(texts, metadata)
        print(f"Ingested {len(all_chunks)} chunks from {len(documents)} documents")


def run_ingestion():
    """Run document ingestion."""
    ingestion = DocumentIngestion()
    ingestion.ingest_all()


if __name__ == "__main__":
    run_ingestion()
