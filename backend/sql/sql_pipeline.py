"""Text-to-SQL pipeline with schema retrieval and self-correction."""
import re
import json
import sqlite3
import time
from typing import Dict, List, Optional, Tuple, Any, Set
from backend.config import settings
from backend.llm.client import get_llm_client
from backend.llm.prompts import SQL_GENERATION_PROMPT, SQL_CORRECTION_PROMPT, SQL_RESULT_SUMMARY_PROMPT
from backend.cache.vector_store import get_schema_store
from backend.sql.schema_cache import get_schemas_by_keywords
from backend.db.session import get_multi_db_connection


def _get_visible_db_names() -> Set[str]:
    """Get set of visible database names from registry."""
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        return set(registry.get_visible_databases().keys())
    except Exception:
        return set()


class SQLPipeline:
    """Handles text-to-SQL conversion with self-correction."""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.max_retries = settings.SQL_MAX_RETRIES

    def retrieve_schemas(self, query: str, top_k: int = None) -> List[Dict]:
        """Retrieve relevant schemas using keyword matching first, then vector search.

        Uses a two-stage approach:
        1. Fast keyword matching (no API calls) - reliable for known terms
        2. FAISS vector search - catches semantic matches keywords might miss

        Results are merged and deduplicated, with keyword matches prioritized.
        Only returns schemas from visible databases.
        """
        top_k = top_k or settings.SCHEMA_TOP_K

        # Get visible databases
        visible_dbs = _get_visible_db_names()

        # --- Stage 1: Keyword-based retrieval (fast, no API calls) ---
        keyword_schemas = get_schemas_by_keywords(query, max_tables=top_k + 4)

        # Filter by visibility
        if visible_dbs:
            keyword_schemas = [s for s in keyword_schemas if s.get("db_name") in visible_dbs]

        # Track which tables we already have (by db_name.table_name)
        seen_tables = set()
        schemas = []
        for s in keyword_schemas:
            table_key = f"{s['db_name']}.{s['table_name']}"
            if table_key not in seen_tables:
                seen_tables.add(table_key)
                schemas.append(s)

        # --- Stage 2: Vector search to fill remaining slots ---
        remaining_slots = max(top_k - len(schemas), 2)  # Always try to add at least 2 more
        try:
            store = get_schema_store()
            search_k = remaining_slots * 3  # Over-fetch to account for duplicates/filtering
            results = store.search(query, top_k=search_k)

            for meta, score in results:
                db_name = meta.get("db_name", "")
                table_name = meta.get("table_name", "")
                table_key = f"{db_name}.{table_name}"

                # Skip duplicates and invisible databases
                if table_key in seen_tables:
                    continue
                if visible_dbs and db_name not in visible_dbs:
                    continue

                seen_tables.add(table_key)
                schemas.append({
                    "db_name": db_name,
                    "table_name": table_name,
                    "description": meta.get("description", ""),
                    "columns": meta.get("columns", []),
                    "ddl": meta.get("ddl", ""),
                    "relevance_score": score
                })

                if len(schemas) >= top_k + 4:  # Allow extra for cross-DB queries
                    break
        except Exception:
            pass  # Keyword results are sufficient if vector search fails

        # --- Cross-database detection: expand limit if query spans multiple DBs ---
        db_names_found = set(s["db_name"] for s in schemas)
        if len(db_names_found) > 1:
            # Cross-database query detected - always include crew_members as join anchor
            crew_members_key = "crew_management.crew_members"
            if crew_members_key not in seen_tables:
                anchor = get_schemas_by_keywords("crew member", max_tables=1)
                if anchor:
                    schemas.insert(0, anchor[0])
            # Allow more schemas for cross-DB queries
            return schemas[:top_k + 4]

        return schemas[:top_k + 2]

    def format_schemas_for_prompt(self, schemas: List[Dict]) -> str:
        """Format schemas for the SQL generation prompt."""
        formatted = []
        for schema in schemas:
            col_str = "\n".join([
                f"    {c['name']} ({c['type']}){' [PK]' if c.get('primary_key') else ''}"
                for c in schema['columns']
            ])
            full_table = f"{schema['db_name']}.{schema['table_name']}"
            formatted.append(f"""
Database: {schema['db_name']}
Table: {schema['table_name']}
Full reference: {full_table}
Description: {schema['description']}
Columns:
{col_str}
""")
        return "\n---\n".join(formatted)

    def generate_sql(self, query: str, schemas: List[Dict]) -> str:
        """Generate SQL from natural language query."""
        schema_text = self.format_schemas_for_prompt(schemas)

        prompt = SQL_GENERATION_PROMPT.format(
            schema_descriptions=schema_text,
            query=query
        )

        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )

        # Clean up SQL
        sql = response.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        return sql

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """Validate SQL for safety."""
        sql_upper = sql.upper()

        # Check for dangerous operations
        forbidden = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE', 'GRANT', 'REVOKE']
        for word in forbidden:
            if re.search(rf'\b{word}\b', sql_upper):
                return False, f"Forbidden operation: {word}"

        # Must be a SELECT statement
        if not sql_upper.strip().startswith('SELECT'):
            return False, "Only SELECT statements are allowed"

        return True, "Valid"

    def execute_sql(self, sql: str, schemas: List[Dict]) -> Tuple[bool, Any, str]:
        """Execute SQL query with all databases attached for cross-DB support."""
        if not schemas:
            return False, None, "No schemas available"

        try:
            conn = get_multi_db_connection()
            cursor = conn.cursor()

            # Set timeout
            cursor.execute(f"PRAGMA busy_timeout = {settings.SQL_TIMEOUT_SECONDS * 1000}")

            # Execute
            cursor.execute(sql)
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = [dict(row) for row in rows]

            # Get column names
            columns = [description[0] for description in cursor.description] if cursor.description else []

            conn.close()

            return True, {"columns": columns, "rows": results, "row_count": len(results)}, ""

        except sqlite3.Error as e:
            return False, None, str(e)
        except Exception as e:
            return False, None, str(e)

    def correct_sql(self, query: str, failed_sql: str, error: str, schemas: List[Dict]) -> str:
        """Attempt to correct failed SQL."""
        schema_text = self.format_schemas_for_prompt(schemas)

        prompt = SQL_CORRECTION_PROMPT.format(
            query=query,
            failed_sql=failed_sql,
            error_message=error,
            schemas=schema_text
        )

        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )

        sql = response.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        return sql

    def summarize_results(self, query: str, sql: str, results: Dict) -> str:
        """Generate a natural language summary of results."""
        prompt = SQL_RESULT_SUMMARY_PROMPT.format(
            query=query,
            sql=sql,
            results=json.dumps(results["rows"][:50], default=str),  # Include up to 50 rows
            row_count=results["row_count"]
        )

        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500  # Increased to handle full crew name listings
        )

        return response.strip()

    def run(self, query: str) -> Dict:
        """Run the full SQL pipeline."""
        start_time = time.time()

        # Step 1: Retrieve relevant schemas
        schemas = self.retrieve_schemas(query)
        if not schemas:
            return {
                "success": False,
                "error": "Could not find relevant database tables for your query",
                "sql": None,
                "results": None,
                "summary": None,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        # Step 2: Generate SQL
        sql = self.generate_sql(query, schemas)

        # Step 3: Validate
        is_valid, validation_msg = self.validate_sql(sql)
        if not is_valid:
            return {
                "success": False,
                "error": f"Generated invalid SQL: {validation_msg}",
                "sql": sql,
                "results": None,
                "summary": None,
                "schemas_used": [s["table_name"] for s in schemas],
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        # Step 4: Execute with retry loop
        last_error = ""
        for attempt in range(self.max_retries):
            success, results, error = self.execute_sql(sql, schemas)

            if success:
                # Generate summary
                summary = self.summarize_results(query, sql, results)

                return {
                    "success": True,
                    "sql": sql,
                    "results": results,
                    "summary": summary,
                    "schemas_used": [s["table_name"] for s in schemas],
                    "attempts": attempt + 1,
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }

            # Attempt correction
            last_error = error
            if attempt < self.max_retries - 1:
                sql = self.correct_sql(query, sql, error, schemas)
                is_valid, validation_msg = self.validate_sql(sql)
                if not is_valid:
                    last_error = validation_msg

        return {
            "success": False,
            "error": f"Failed after {self.max_retries} attempts. Last error: {last_error}",
            "sql": sql,
            "results": None,
            "summary": None,
            "schemas_used": [s["table_name"] for s in schemas],
            "processing_time_ms": int((time.time() - start_time) * 1000)
        }
