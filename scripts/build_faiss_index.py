"""Build FAISS vector indexes from schema_metadata and document_chunks.

Uses hand-written descriptions from schema_metadata (no LLM needed for descriptions).
Only requires LLM API for embedding generation.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings
from backend.db.session import DB_MAPPING
from backend.cache.vector_store import get_schema_store, get_document_store


def build_schema_index():
    """Build FAISS index for schema search using pre-populated metadata."""
    print("Building schema FAISS index...")

    # Read descriptions from schema_metadata
    app_conn = sqlite3.connect(settings.app_db_path)
    app_conn.row_factory = sqlite3.Row
    app_c = app_conn.cursor()

    app_c.execute("SELECT db_name, table_name, llm_description, ddl_statement FROM schema_metadata")
    meta_rows = app_c.fetchall()
    app_conn.close()

    if not meta_rows:
        print("ERROR: schema_metadata is empty. Run populate_schema_metadata.py first.")
        return False

    descriptions = {}
    ddl_map = {}
    for row in meta_rows:
        key = (row['db_name'], row['table_name'])
        descriptions[key] = row['llm_description']
        ddl_map[key] = row['ddl_statement'] or ""

    # Crawl actual column info from databases (no LLM needed)
    texts = []
    metadata = []

    for db_name, db_path in DB_MAPPING.items():
        if db_name == "app":
            continue
        if not os.path.exists(db_path):
            print(f"  Skipping {db_name} - not found")
            continue

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_names = [r['name'] for r in c.fetchall()]

        for table_name in table_names:
            # Get column info
            c.execute(f"PRAGMA table_info([{table_name}])")
            columns = []
            for col in c.fetchall():
                columns.append({
                    "name": col['name'],
                    "type": col['type'],
                    "nullable": not col['notnull'],
                    "primary_key": bool(col['pk']),
                    "default": col['dflt_value']
                })

            # Get row count
            c.execute(f"SELECT COUNT(*) as cnt FROM [{table_name}]")
            row_count = c.fetchone()['cnt']

            # Get description from pre-populated metadata
            key = (db_name, table_name)
            description = descriptions.get(
                key,
                f"{db_name}.{table_name} - contains {row_count} rows"
            )
            ddl = ddl_map.get(key, "")

            # Build searchable text
            col_names = ", ".join([col['name'] for col in columns])
            search_text = f"{db_name}.{table_name}: {description}. Columns: {col_names}"

            texts.append(search_text)
            metadata.append({
                "db_name": db_name,
                "table_name": table_name,
                "description": description,
                "columns": columns,
                "ddl": ddl,
                "row_count": row_count
            })

            print(f"  {db_name}.{table_name}")

        conn.close()

    if not texts:
        print("No tables found to index.")
        return False

    # Build FAISS index
    store = get_schema_store()
    store.clear()
    print(f"\nGenerating embeddings for {len(texts)} tables...")
    store.add(texts, metadata)
    print(f"Schema FAISS index built with {store.count} entries.")
    return True


def build_document_index():
    """Build FAISS index for RAG document search."""
    print("\nBuilding document FAISS index...")

    app_conn = sqlite3.connect(settings.app_db_path)
    app_conn.row_factory = sqlite3.Row
    app_c = app_conn.cursor()

    # Check if document_chunks table exists and has data
    try:
        app_c.execute("SELECT COUNT(*) as cnt FROM document_chunks")
        count = app_c.fetchone()['cnt']
    except sqlite3.OperationalError:
        print("  document_chunks table not found. Run ingest_documents.py first.")
        app_conn.close()
        return False

    if count == 0:
        print("  No document chunks found. Run ingest_documents.py first.")
        app_conn.close()
        return False

    app_c.execute("SELECT chunk_id, document_name, section_title, content FROM document_chunks")
    chunks = app_c.fetchall()
    app_conn.close()

    texts = []
    metadata = []
    for chunk in chunks:
        texts.append(chunk['content'])
        metadata.append({
            "chunk_id": chunk['chunk_id'],
            "document_name": chunk['document_name'],
            "section_title": chunk['section_title'],
            "content": chunk['content']
        })

    store = get_document_store()
    store.clear()
    print(f"  Generating embeddings for {len(texts)} document chunks...")
    store.add(texts, metadata)
    print(f"  Document FAISS index built with {store.count} entries.")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  FAISS Index Builder")
    print("=" * 60)

    if not settings.LLM_API_KEY:
        print("\nERROR: LLM_API_KEY not set. Embeddings require the API.")
        print("Set LLM_CHAT_URL and LLM_API_KEY in your .env file and try again.")
        sys.exit(1)

    schema_ok = build_schema_index()

    # Try documents too (may not be ingested yet)
    doc_ok = build_document_index()

    print("\n" + "=" * 60)
    print(f"  Schema index: {'OK' if schema_ok else 'FAILED'}")
    print(f"  Document index: {'OK' if doc_ok else 'SKIPPED (no chunks yet)'}")
    print("=" * 60)
