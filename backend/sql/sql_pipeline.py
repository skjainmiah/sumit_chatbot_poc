"""V1 text-to-SQL pipeline - uses keyword + FAISS schema retrieval, then generates and executes SQL."""
import re
import json
import sqlite3
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from backend.config import settings
from backend.llm.client import get_llm_client
from backend.llm.prompts import SQL_GENERATION_PROMPT, SQL_GENERATION_WITH_CONTEXT_PROMPT, SQL_CORRECTION_PROMPT, SQL_RESULT_SUMMARY_PROMPT, SQL_RESULT_STATS_SUMMARY_PROMPT
from backend.cache.vector_store import get_schema_store
from backend.sql.schema_cache import get_schemas_by_keywords
from backend.db.session import get_multi_db_connection

logger = logging.getLogger("chatbot.sql.pipeline_v1")


def _get_visible_db_names() -> Optional[Set[str]]:
    """Get set of visible database names from registry.

    Returns None if the registry is unavailable (treat as 'show all'),
    or a (possibly empty) set of visible db names.
    """
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        return set(registry.get_visible_databases().keys())
    except Exception:
        return None


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

        # Get all databases
        all_dbs = _get_visible_db_names()
        logger.info(f"[retrieve_schemas] query=\"{query[:80]}\" top_k={top_k} registry_dbs={all_dbs if all_dbs is not None else 'UNAVAILABLE'}")

        # --- Stage 1: Keyword-based retrieval (fast, no API calls) ---
        keyword_schemas = get_schemas_by_keywords(query, max_tables=top_k + 4)
        logger.info(f"[retrieve_schemas] Keyword match returned {len(keyword_schemas)} schemas: "
                     f"{[s.get('db_name') + '.' + s.get('table_name') for s in keyword_schemas[:5]]}")

        # Filter by registered databases (None = registry unavailable, skip filter)
        if all_dbs is not None:
            before_count = len(keyword_schemas)
            keyword_schemas = [s for s in keyword_schemas if s.get("db_name") in all_dbs]
            if before_count != len(keyword_schemas):
                logger.warning(f"[retrieve_schemas] Registry filter removed {before_count - len(keyword_schemas)} schemas "
                               f"(registry has: {all_dbs})")

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
                if all_dbs is not None and db_name not in all_dbs:
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

    def generate_sql(self, query: str, schemas: List[Dict], context: str = "") -> str:
        """Generate SQL from natural language query, optionally with conversation context.

        Retries once if the LLM returns empty content (corporate API intermittent issue).
        """
        schema_text = self.format_schemas_for_prompt(schemas)

        if context:
            prompt = SQL_GENERATION_WITH_CONTEXT_PROMPT.format(
                conversation_context=context,
                schema_descriptions=schema_text,
                query=query
            )
        else:
            prompt = SQL_GENERATION_PROMPT.format(
                schema_descriptions=schema_text,
                query=query
            )

        logger.info(f"[generate_sql] Sending query to LLM with {len(schemas)} schemas, prompt_len={len(prompt)}")

        # Try up to 2 times (LLM sometimes returns empty response)
        for attempt in range(2):
            step_start = time.time()
            response = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1000
            )
            step_ms = int((time.time() - step_start) * 1000)

            # Clean up SQL
            sql = response.strip()
            sql = sql.replace("```sql", "").replace("```", "").strip()

            if sql:
                logger.info(f"[generate_sql] LLM responded in {step_ms}ms | sql=\"{sql[:150]}\"")
                return sql

            # Empty response — retry once
            if attempt == 0:
                logger.warning(f"[generate_sql] LLM returned empty SQL after {step_ms}ms, retrying...")
            else:
                logger.error(f"[generate_sql] LLM returned empty SQL on retry after {step_ms}ms")

        return ""

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
            logger.warning("[execute_sql] No schemas available, skipping execution")
            return False, None, "No schemas available"

        step_start = time.time()
        logger.info(f"[execute_sql] Executing: {sql[:200]}")
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

            query_results = {"columns": columns, "rows": results, "row_count": len(results)}

            step_ms = int((time.time() - step_start) * 1000)
            logger.info(f"[execute_sql] OK {step_ms}ms | {len(results)} rows, {len(columns)} columns")
            return True, query_results, ""

        except sqlite3.Error as e:
            step_ms = int((time.time() - step_start) * 1000)
            logger.error(f"[execute_sql] SQLite error after {step_ms}ms: {e}")
            return False, None, str(e)
        except Exception as e:
            step_ms = int((time.time() - step_start) * 1000)
            logger.error(f"[execute_sql] Error after {step_ms}ms: {e}")
            return False, None, str(e)

    def correct_sql(self, query: str, failed_sql: str, error: str, schemas: List[Dict]) -> str:
        """Attempt to correct failed SQL."""
        logger.info(f"[correct_sql] Correcting failed SQL | error={error[:150]}")
        schema_text = self.format_schemas_for_prompt(schemas)

        prompt = SQL_CORRECTION_PROMPT.format(
            query=query,
            failed_sql=failed_sql,
            error_message=error,
            schemas=schema_text
        )

        step_start = time.time()
        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )

        sql = response.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        step_ms = int((time.time() - step_start) * 1000)
        logger.info(f"[correct_sql] LLM corrected in {step_ms}ms | new_sql=\"{sql[:150]}\"")
        return sql

    def _parse_suggestions(self, text: str):
        """Extract follow-up suggestions from summary text. Returns (clean_summary, suggestions_list)."""
        lines = text.strip().split("\n")
        suggestions = []
        summary_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("SUGGESTION:"):
                suggestion = stripped[len("SUGGESTION:"):].strip()
                if suggestion:
                    suggestions.append(suggestion)
            else:
                summary_lines.append(line)
        clean_summary = "\n".join(summary_lines).rstrip()
        return clean_summary, suggestions[:3]

    # Threshold: if results exceed this, use stats-based summarization
    LARGE_RESULT_THRESHOLD = 50

    def summarize_results(self, query: str, sql: str, results: Dict) -> tuple:
        """Generate a natural language summary with follow-up suggestions. Returns (summary, suggestions).

        For small results (<50 rows): sends actual rows to LLM.
        For large results (>=50 rows): computes stats from ALL rows server-side,
        sends only stats to LLM for accurate summarization.
        """
        row_count = results["row_count"]
        all_rows = results["rows"]

        if row_count >= self.LARGE_RESULT_THRESHOLD:
            return self._summarize_with_stats(query, sql, all_rows, row_count)
        else:
            return self._summarize_with_rows(query, sql, all_rows, row_count)

    def _summarize_with_rows(self, query: str, sql: str, rows: list, row_count: int) -> tuple:
        """Summarize small result sets by sending actual rows to LLM."""
        max_rows = 25
        rows_for_summary = rows[:max_rows]
        truncated_rows = []
        for row in rows_for_summary:
            truncated_row = {}
            for k, v in row.items():
                sv = str(v) if v is not None else ""
                truncated_row[k] = sv[:200] if len(sv) > 200 else v
            truncated_rows.append(truncated_row)

        prompt = SQL_RESULT_SUMMARY_PROMPT.format(
            query=query,
            sql=sql,
            results=json.dumps(truncated_rows, default=str),
            row_count=row_count
        )

        logger.info(f"[summarize] Small result ({row_count} rows), sending {len(truncated_rows)} rows to LLM")
        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return self._parse_suggestions(response)

    def _summarize_with_stats(self, query: str, sql: str, rows: list, row_count: int) -> tuple:
        """Summarize large result sets using pre-computed statistics from ALL rows."""
        from collections import Counter

        logger.info(f"[summarize] Large result ({row_count} rows), computing stats from ALL rows")

        columns = list(rows[0].keys()) if rows else []
        stats_lines = []
        distribution_lines = []

        for col in columns:
            values = [row.get(col) for row in rows]
            non_null = [v for v in values if v is not None and str(v).strip() != ""]
            null_count = len(values) - len(non_null)

            numeric_values = []
            for v in non_null:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass

            is_numeric = len(numeric_values) > len(non_null) * 0.8 if non_null else False

            if is_numeric and numeric_values:
                avg_val = sum(numeric_values) / len(numeric_values)
                min_val = min(numeric_values)
                max_val = max(numeric_values)
                if all(v == int(v) for v in numeric_values):
                    stats_lines.append(
                        f"  {col}: numeric | count={len(non_null)} | "
                        f"min={int(min_val):,} | max={int(max_val):,} | avg={avg_val:,.1f}"
                        f"{f' | {null_count} nulls' if null_count else ''}"
                    )
                else:
                    stats_lines.append(
                        f"  {col}: numeric | count={len(non_null)} | "
                        f"min={min_val:,.2f} | max={max_val:,.2f} | avg={avg_val:,.2f}"
                        f"{f' | {null_count} nulls' if null_count else ''}"
                    )
            else:
                distinct_count = len(set(str(v) for v in non_null))
                stats_lines.append(
                    f"  {col}: text | count={len(non_null)} | distinct={distinct_count}"
                    f"{f' | {null_count} nulls' if null_count else ''}"
                )

            str_values = [str(v) for v in non_null]
            distinct_vals = set(str_values)

            if 1 < len(distinct_vals) <= 50:
                counts = Counter(str_values)
                top_items = counts.most_common(15)
                total = len(str_values)
                dist_parts = []
                for val, count in top_items:
                    pct = (count / total) * 100
                    display_val = val[:60] + "..." if len(val) > 60 else val
                    dist_parts.append(f"    {display_val}: {count:,} ({pct:.1f}%)")
                remaining = len(distinct_vals) - len(top_items)
                header = f"  {col} (top {len(top_items)}" + (f", +{remaining} others):" if remaining > 0 else "):")
                distribution_lines.append(header)
                distribution_lines.extend(dist_parts)
            elif len(distinct_vals) == 1:
                distribution_lines.append(f"  {col}: all values = \"{list(distinct_vals)[0]}\"")

        # Small sample for format reference only
        sample_rows = rows[:5]
        truncated_sample = []
        for row in sample_rows:
            truncated_row = {}
            for k, v in row.items():
                sv = str(v) if v is not None else ""
                truncated_row[k] = sv[:100] if len(sv) > 100 else v
            truncated_sample.append(truncated_row)

        prompt = SQL_RESULT_STATS_SUMMARY_PROMPT.format(
            query=query,
            sql=sql,
            row_count=row_count,
            column_stats="\n".join(stats_lines) if stats_lines else "No column stats available",
            value_distributions="\n".join(distribution_lines) if distribution_lines else "No categorical distributions",
            sample_note=f"Sample rows (5 of {row_count}, for format reference only):\n{json.dumps(truncated_sample, default=str)}"
        )

        logger.info(f"[summarize] Stats prompt length: {len(prompt)} chars")
        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return self._parse_suggestions(response)

    def summarize_no_results(self, query: str, sql: str) -> tuple:
        """Generate a natural language explanation when a query returns zero rows."""
        no_results_prompt = (
            f"The user asked: \"{query}\"\n\n"
            f"The SQL query executed was:\n{sql}\n\n"
            f"The query returned 0 rows (no matching data found).\n\n"
            f"Please provide a helpful, natural language response that:\n"
            f"1. Acknowledges what the user was looking for\n"
            f"2. Explains in a friendly way that no matching data was found\n"
            f"3. Suggests possible reasons (e.g., different naming conventions, date ranges, spelling variations)\n"
            f"4. Offers helpful alternatives or suggestions to refine their search\n\n"
            f"Do NOT say 'No records found' or use technical SQL language. "
            f"Be conversational and helpful, as if you're a knowledgeable colleague.\n\n"
            f"After your response, add exactly 3 follow-up suggestions the user might try, "
            f"each on a separate line prefixed with 'SUGGESTION:'"
        )

        logger.info(f"[summarize_no_results] Generating natural response for zero-row result")
        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": no_results_prompt}],
            temperature=0.4,
            max_tokens=1000
        )
        return self._parse_suggestions(response)

    def run(self, query: str, context: str = "") -> Dict:
        """Run the full SQL pipeline.

        Args:
            query: The user's natural language question.
            context: Optional conversation context (recent turns) for follow-up handling.
        """
        start_time = time.time()
        logger.info(f"[pipeline] START query=\"{query[:120]}\" context_len={len(context)}")

        # Step 1: Retrieve relevant schemas
        schemas = self.retrieve_schemas(query)
        if not schemas:
            logger.warning("[pipeline] No schemas found for query")
            return {
                "success": False,
                "error": "Could not find relevant database tables for your query",
                "sql": None,
                "results": None,
                "summary": None,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }

        # Step 2: Generate SQL (with conversation context if available)
        logger.info(f"[pipeline] Using {len(schemas)} schemas: {[s['db_name']+'.'+s['table_name'] for s in schemas[:5]]}")
        sql = self.generate_sql(query, schemas, context)

        # Step 3: Validate (if fails and we had context, retry without context)
        is_valid, validation_msg = self.validate_sql(sql)
        if not is_valid and context:
            logger.warning(f"[pipeline] SQL validation failed with context: {validation_msg}, retrying without context")
            sql = self.generate_sql(query, schemas, context="")
            is_valid, validation_msg = self.validate_sql(sql)

        if not is_valid:
            logger.warning(f"[pipeline] SQL validation failed: {validation_msg}")
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
        used_context_retry = False
        for attempt in range(self.max_retries):
            logger.info(f"[pipeline] Execute attempt {attempt + 1}/{self.max_retries}")
            success, results, error = self.execute_sql(sql, schemas)

            if success:
                # Generate summary with follow-up suggestions
                logger.info(f"[pipeline] SQL executed OK | {results['row_count']} rows")
                masked_results = None

                if results["row_count"] == 0 and context and not used_context_retry:
                    # Zero rows with context — retry WITHOUT context as safety net
                    # Context may have caused the LLM to generate wrong JOINs
                    logger.info("[pipeline] Zero rows with context, retrying without context")
                    used_context_retry = True
                    sql = self.generate_sql(query, schemas, context="")
                    is_valid, validation_msg = self.validate_sql(sql)
                    if is_valid:
                        success2, results2, error2 = self.execute_sql(sql, schemas)
                        if success2 and results2["row_count"] > 0:
                            logger.info(f"[pipeline] Context-free retry returned {results2['row_count']} rows")
                            results = results2
                        else:
                            logger.info("[pipeline] Context-free retry also returned 0 rows, using original")

                if results["row_count"] == 0:
                    # No data found — use LLM to generate a natural, context-aware response
                    logger.info("[pipeline] Zero rows returned, generating natural language response")
                    try:
                        summary, suggestions = self.summarize_no_results(query, sql)
                        if not summary or not summary.strip():
                            summary = ("I looked through the database for your query but couldn't find any matching results. "
                                       "This could mean the data doesn't exist yet, or the search criteria might need adjusting. "
                                       "Could you try rephrasing or broadening your search?")
                    except Exception as e:
                        logger.warning(f"[pipeline] No-results summarization failed: {e}")
                        summary = ("I couldn't find any data matching your question. "
                                   "The specific criteria you mentioned may not have corresponding entries in the database. "
                                   "Try adjusting your search terms or ask me what data is available.")
                        suggestions = []
                else:
                    # Mask sensitive columns before LLM summarization (user still sees real data)
                    import copy
                    from backend.pii.column_masker import mask_query_results
                    masked_results = mask_query_results(copy.deepcopy(results), sql)

                    # Log masked vs original for PII audit
                    masked_cols = [c for c in masked_results.get("columns", [])
                                   if masked_results["rows"] and masked_results["rows"][0].get(c) == "[MASKED]"]
                    if masked_cols:
                        sample = masked_results["rows"][0] if masked_results["rows"] else {}
                        logger.info(f"[PII column_mask] Columns masked for LLM: {masked_cols}")
                        logger.info(f"[PII column_mask] Sample row sent to LLM: {sample}")

                    summary, suggestions = self.summarize_results(query, sql, masked_results)
                    # Guard against empty LLM summary
                    if not summary or not summary.strip():
                        summary = f"Query returned {results['row_count']} row(s)."
                        logger.warning("[pipeline] LLM returned empty summary, using fallback")

                elapsed = int((time.time() - start_time) * 1000)
                logger.info(f"[pipeline] DONE success | attempts={attempt + 1} | {elapsed}ms | {results['row_count']} rows")
                return {
                    "success": True,
                    "sql": sql,
                    "results": results,
                    "masked_results": masked_results if results["row_count"] > 0 else None,
                    "summary": summary,
                    "suggestions": suggestions,
                    "schemas_used": [s["table_name"] for s in schemas],
                    "attempts": attempt + 1,
                    "processing_time_ms": elapsed
                }

            # Attempt correction
            last_error = error
            if attempt < self.max_retries - 1:
                logger.info(f"[pipeline] SQL failed, attempting correction (attempt {attempt + 1})")
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
