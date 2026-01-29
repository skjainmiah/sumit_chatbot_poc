"""Ingest policy documents into the RAG vector store."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag.document_ingestion import DocumentIngestion
from backend.config import settings


def ingest_documents():
    """Ingest all policy documents."""
    print("=" * 60)
    print("Document Ingestion")
    print("=" * 60)

    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "policy_documents")

    if not os.path.exists(docs_dir):
        print(f"Error: Documents directory not found at {docs_dir}")
        return

    # List documents
    md_files = [f for f in os.listdir(docs_dir) if f.endswith('.md')]
    print(f"\nFound {len(md_files)} documents:")
    for f in md_files:
        print(f"  - {f}")

    # Initialize ingestion
    print("\nInitializing document ingestion...")
    ingestion = DocumentIngestion()

    # Ingest all documents
    print("\nIngesting documents...")
    ingestion.ingest_all(docs_dir)

    print("\n" + "=" * 60)
    print("Document ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    ingest_documents()
