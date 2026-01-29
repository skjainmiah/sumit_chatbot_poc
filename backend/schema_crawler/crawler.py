"""Schema crawler - extracts schema information from all databases."""
import sqlite3
import json
from typing import List, Dict
from pathlib import Path
from backend.config import settings
from backend.db.session import DB_MAPPING
from backend.llm.client import get_llm_client
from backend.llm.prompts import SCHEMA_DESCRIPTION_PROMPT
from backend.cache.vector_store import get_schema_store


class SchemaCrawler:
    """Crawls all databases and extracts schema information."""

    def __init__(self):
        self.llm_client = get_llm_client()

    def crawl_database(self, db_name: str, db_path: str) -> List[Dict]:
        """Crawl a single database and extract table schemas."""
        if not Path(db_path).exists():
            print(f"Database not found: {db_path}")
            return []

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        tables = []

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_names = [row['name'] for row in cursor.fetchall()]

        for table_name in table_names:
            # Get column info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for col in cursor.fetchall():
                columns.append({
                    "name": col['name'],
                    "type": col['type'],
                    "nullable": not col['notnull'],
                    "primary_key": bool(col['pk']),
                    "default": col['dflt_value']
                })

            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = []
            for fk in cursor.fetchall():
                foreign_keys.append({
                    "column": fk['from'],
                    "references_table": fk['table'],
                    "references_column": fk['to']
                })

            # Get row count
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            row_count = cursor.fetchone()['cnt']

            # Get sample data (3 rows)
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_rows = [dict(row) for row in cursor.fetchall()]

            # Get DDL
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            ddl_result = cursor.fetchone()
            ddl = ddl_result['sql'] if ddl_result else ""

            tables.append({
                "db_name": db_name,
                "table_name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "row_count": row_count,
                "sample_data": sample_rows,
                "ddl": ddl
            })

        conn.close()
        return tables

    def generate_description(self, table_info: Dict) -> str:
        """Generate LLM description for a table."""
        columns_str = "\n".join([
            f"  - {c['name']} ({c['type']}){' [PK]' if c['primary_key'] else ''}"
            for c in table_info['columns']
        ])

        sample_str = json.dumps(table_info['sample_data'][:2], indent=2, default=str)

        prompt = SCHEMA_DESCRIPTION_PROMPT.format(
            db_name=table_info['db_name'],
            table_name=table_info['table_name'],
            columns=columns_str,
            sample_data=sample_str
        )

        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200
        )

        return response.strip()

    def crawl_all(self, generate_descriptions: bool = True) -> List[Dict]:
        """Crawl all databases and optionally generate descriptions."""
        all_tables = []

        # Skip app database
        databases = {k: v for k, v in DB_MAPPING.items() if k != 'app'}

        for db_name, db_path in databases.items():
            print(f"Crawling {db_name}...")
            tables = self.crawl_database(db_name, db_path)

            for table in tables:
                if generate_descriptions:
                    print(f"  Generating description for {table['table_name']}...")
                    table['description'] = self.generate_description(table)
                else:
                    # Simple description
                    table['description'] = f"{table['db_name']}.{table['table_name']} - contains {table['row_count']} rows"

                all_tables.append(table)

        return all_tables

    def index_schemas(self, tables: List[Dict] = None):
        """Index schema descriptions into vector store."""
        if tables is None:
            tables = self.crawl_all(generate_descriptions=True)

        store = get_schema_store()
        store.clear()  # Clear existing

        texts = []
        metadata = []

        for table in tables:
            # Create searchable text combining description and column names
            col_names = ", ".join([c['name'] for c in table['columns']])
            search_text = f"{table['db_name']}.{table['table_name']}: {table['description']}. Columns: {col_names}"

            texts.append(search_text)
            metadata.append({
                "db_name": table['db_name'],
                "table_name": table['table_name'],
                "description": table['description'],
                "columns": table['columns'],
                "ddl": table['ddl'],
                "row_count": table['row_count']
            })

        store.add(texts, metadata)
        print(f"Indexed {len(tables)} table schemas")


def run_crawler():
    """Run the schema crawler."""
    crawler = SchemaCrawler()
    crawler.index_schemas()


if __name__ == "__main__":
    run_crawler()
