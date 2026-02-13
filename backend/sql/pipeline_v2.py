"""
V2 SQL pipeline - sends the full schema in the prompt instead of using FAISS retrieval.
Handles meta questions (about DB structure) directly, generates SQL for data queries,
and does self-correction if the first attempt fails.
"""

import re
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from backend.config import settings
from backend.llm.client import get_llm_client
from backend.llm.prompts import SQL_CORRECTION_PROMPT, SQL_RESULT_SUMMARY_PROMPT, SQL_RESULT_STATS_SUMMARY_PROMPT
from backend.schema.loader import get_schema_loader
from backend.db.session import get_multi_db_connection

logger = logging.getLogger("chatbot.sql.pipeline_v2")


class QueryIntent(Enum):
    META = "meta"           # Questions about database structure
    DATA = "data"           # Questions requiring SQL
    AMBIGUOUS = "ambiguous" # Needs clarification
    GENERAL = "general"     # Greetings, chitchat


# Few-shot examples for SQL generation - customize these for your schema
FEW_SHOT_EXAMPLES = """
EXAMPLE QUERIES AND RESPONSES:

Example 1 - Simple query:
Q: "Show all employees"
Response: {{"intent": "data", "response": {{"sql": "SELECT * FROM hr_payroll.employees LIMIT 100;", "explanation": "Retrieves all employee records"}}}}

Example 2 - Aggregation:
Q: "How many flights were scheduled last month?"
Response: {{"intent": "data", "response": {{"sql": "SELECT COUNT(*) as flight_count FROM flight_operations.flights WHERE scheduled_date >= date('now', 'start of month', '-1 month') AND scheduled_date < date('now', 'start of month');", "explanation": "Counts flights from the previous calendar month"}}}}

Example 3 - JOIN query:
Q: "List crew members with their assignment details"
Response: {{"intent": "data", "response": {{"sql": "SELECT cm.first_name, cm.last_name, ca.assignment_type FROM crew_management.crew_members cm JOIN crew_management.crew_assignments ca ON cm.crew_id = ca.crew_id LIMIT 100;", "explanation": "Joins crew members with assignments"}}}}

Example 4 - Meta question:
Q: "What databases are available?"
Response: {{"intent": "meta", "response": {{"answer": "The available databases are listed dynamically from the registry. Use the meta handler to get the current list."}}}}

Example 5 - Ambiguous question:
Q: "Show me John's data"
Response: {{"intent": "ambiguous", "response": {{"clarification": "There may be multiple people named John. Could you provide a last name or employee ID? Also, what specific information are you looking for (contact info, salary, assignments)?"}}}}
"""


SYSTEM_PROMPT = """You are an expert SQL assistant. Your job is to help users query databases.

CRITICAL RULES:
1. Always use FULLY QUALIFIED table names: database_name.table_name
   Example: hr_payroll.employees (NOT just "employees")
   Note: Do NOT include schema name - use database_name.table_name format only.
2. Only generate SELECT statements - NEVER INSERT, UPDATE, DELETE, DROP, ALTER, CREATE
3. Do NOT add LIMIT unless the user explicitly asks for a specific number of results (e.g., "top 10", "first 5"). Always return all matching rows so aggregations and summaries are accurate.
4. Use SQLite-compatible syntax:
   - Date functions: date(), datetime(), strftime(), date('now'), date('now', '-1 month')
   - Use COALESCE, CASE WHEN, GROUP BY, ORDER BY as normal
   - String concatenation: use || operator
   - Use LIKE for pattern matching (case-insensitive by default in SQLite)
5. Use meaningful column aliases for readability
6. For JOINs, always specify the join condition clearly
7. Cross-database JOINs are supported: JOIN other_db.table_name ON ...
8. For cross-database queries, JOIN on common columns like employee_id across databases.
9. When asking about people/crew, include name columns if available in the schemas provided.
10. When the question mentions "unawarded" or "not awarded", filter crew_roster.roster_status = 'Not Awarded'
11. For multi-database questions, use JOINs across databases freely via shared columns.
12. IMPORTANT: Search ALL provided schemas for the requested data. Do NOT assume data only exists in one database. If looking for an employee by ID, search across all tables that have an employee/ID column using UNION ALL if needed.
13. When choosing which table to query, carefully read the column names in the schemas. Pick the table whose columns best match what the user is asking for. For employee lookups, start from the table with the most person-related columns (name, ID, role, status, etc.), not auxiliary/lookup tables.
14. Do NOT invent or guess table names or column names. Only use tables and columns that appear in the schema provided below.

CRITICAL DATA VALUE REFERENCE:
- combineddatalax.sheet1.EmployeeID is INTEGER (range: 46496-774459, 130 distinct employees)
- combineddatalax.sheet1.SequenceID is INTEGER with only 4 valid values: 801111, 801112, 801114, 801116
- combineddatalax.sheet1.SequencePosition is INTEGER (values: 1, 3, 4, 5)
- combineddatalax.sheet1.LegalityContextsID is INTEGER (values: 1, 2, 3, 4, 9, 10)
- combineddatalax.sheet1.LegalityContextID is INTEGER (values: 1, 2, 3, 4, 9, 10)
- combineddatalax.sheet1.IsLegal is INTEGER (0=Not Legal, 1=Legal)
- combineddatalax.sheet1.LegalityPhaseID is INTEGER (values: 1, 3)
- combineddatalax.sheet1.QLARuleName is TEXT (e.g., '24X7REST(IL)', 'TOUCHFD(NC)', 'DBLSTBY(IL)', 'RSTREQ(IL)', 'SpkrQualCheck')
- combineddatalax.sheet1.BaseCD is TEXT (all values are 'LAX')
- combineddatalax.sheet1.SequenceNumber is INTEGER — this is the human-readable sequence number that users refer to (e.g., 3715, 4201, etc.)
- CRITICAL: When a user says "sequence 3715" or any sequence number NOT in the 800000+ range, ALWAYS use SequenceNumber (NOT SequenceID). SequenceID only has 4 internal values (801111-801116). Users almost always mean SequenceNumber.
- crew_roster.roster_month is TEXT with full month names: 'January', 'February', 'March', 'April', 'May', 'June', etc.
- crew_roster.roster_year is INTEGER: 2025
- crew_roster.roster_status values: 'Awarded', 'Reserve', 'Standby', 'Not Awarded', 'Training', 'Leave', 'Mixed'
- crew_roster.not_awarded_reason values: 'Seniority', 'Qualification Gap', 'Schedule Conflict', 'Base Mismatch', 'Medical Hold', 'Training Conflict', 'Visa Issue', 'Staffing Requirement', 'Bid Not Submitted', 'Pairing Unavailable', 'Rest Requirement', 'Disciplinary Action', 'Probation Period', 'Union Dispute', 'Crew Complement Full', 'Aircraft Type Mismatch', 'Insufficient Flight Hours', 'Administrative Error', 'Voluntary Withdrawal', 'FAA Restriction', 'Fatigue Risk Flag'
- crew_roster.duty_type values: 'Line Flying', 'Reserve', 'Standby', 'Training', 'Leave', 'Admin', 'Mixed'
- crew_members.crew_role values: 'Captain', 'First Officer', 'Senior First Officer', 'Flight Engineer', 'Purser', 'Senior Cabin Crew', 'Cabin Crew', 'Trainee'
- crew_members.status values: 'Active', 'On Leave', 'Suspended', 'Inactive', 'Retired'
- flights.flight_status values: 'Scheduled', 'Boarding', 'Departed', 'In Air', 'Landed', 'Arrived', 'Cancelled', 'Diverted', 'Delayed'
- leave_records.leave_type values: 'Annual Leave', 'Sick Leave', 'Emergency Leave', 'Training Leave'

AVAILABLE SCHEMA:
{schema}

{examples}

RESPONSE FORMAT:
You MUST respond with valid JSON only. No markdown, no explanations outside JSON.
"""


USER_PROMPT_TEMPLATE = """Question: {question}

{context}

Respond with JSON in this exact format:
{{
    "intent": "meta" | "data" | "ambiguous",
    "response": {{
        "answer": "For meta questions only - direct answer about database structure",
        "sql": "For data questions only - the SELECT query",
        "explanation": "For data questions only - brief explanation",
        "clarification": "For ambiguous questions only - what you need to know"
    }}
}}

Only include the relevant fields for the intent type. Respond with valid JSON only."""


class SQLPipelineV2:
    """Improved Text-to-SQL pipeline with full schema approach."""

    def __init__(self):
        self.llm = get_llm_client()
        self.schema_loader = get_schema_loader()
        self.max_retries = getattr(settings, 'SQL_MAX_RETRIES', 2)
        self.query_timeout = getattr(settings, 'SQL_TIMEOUT_SECONDS', 30)

    def _get_system_prompt(self) -> str:
        """Build system prompt with current visible schema.

        Regenerated on each call so visibility changes take effect immediately.
        """
        return SYSTEM_PROMPT.format(
            schema=self.schema_loader.get_schema_text(),
            examples=FEW_SHOT_EXAMPLES
        )

    def _detect_meta_question(self, question: str) -> bool:
        """Quick check for meta-questions that don't need LLM."""
        meta_patterns = [
            # Database questions
            r'\b(list|show|what|which|get|display)\b.*\b(database|databases|db|dbs)\b',
            r'\bdatabases?\s*(available|exist|do (we|you) have)',
            r'\bhow many\b.*\bdatabases?\b',
            # Table questions
            r'\b(list|show|what|which|get|display)\b.*\btables?\b',
            r'\btables?\s*(available|exist|in)',
            r'\bhow many\b.*\btables?\b',
            r'\bwhat tables\b',
            # Schema/structure questions
            r'\b(describe|structure|schema|columns?)\b.*\b(database|table|db)\b',
            r'\bavailable\b.*\b(database|table)',
            r'\bwhat (is|are) the (schema|structure|columns)',
            # Count questions
            r'\b(how many|count|number of)\b.*\b(table|column|database)',
        ]
        question_lower = question.lower()
        return any(re.search(p, question_lower) for p in meta_patterns)

    def _answer_meta_question(self, question: str) -> Dict:
        """Answer meta-questions directly without SQL."""
        question_lower = question.lower()
        schema_loader = self.schema_loader
        schema_data = schema_loader.get_schema_data()
        visible_db_names = set(schema_loader.get_database_names(visible_only=True))

        # List databases (including "how many databases" questions)
        if re.search(r'\b(list|show|what|which|get|display|available|how many|count|number of)\b.*\bdatabase', question_lower):
            db_names = list(visible_db_names)
            # Also get table counts per database (only visible ones)
            db_details = []
            for db in schema_data.get("databases", []):
                if db["name"] in visible_db_names:
                    db_details.append(f"  • {db['name']} ({len(db.get('tables', []))} tables)")

            return {
                "success": True,
                "intent": "meta",
                "answer": f"There are {len(db_names)} databases available:\n" + "\n".join(db_details),
                "sql": None,
                "results": None
            }

        # List tables (check for specific database first)
        if re.search(r'\b(list|show|what|which|get|display|available|how many|count|number of)\b.*\btable', question_lower):
            # Check if specific database mentioned
            db_match = None
            for db in schema_loader.get_database_names():
                if db.lower() in question_lower:
                    db_match = db
                    break

            tables = schema_loader.get_table_names(db_match)
            db_qualifier = f" in {db_match}" if db_match else ""

            return {
                "success": True,
                "intent": "meta",
                "answer": f"There are {len(tables)} tables{db_qualifier}:\n" +
                          "\n".join(f"  • {t}" for t in tables[:50]) +
                          (f"\n  ... and {len(tables) - 50} more" if len(tables) > 50 else ""),
                "sql": None,
                "results": None
            }

        # Describe table / show columns
        if re.search(r'\b(describe|columns?|structure|schema)\b.*\b(table|for)\b', question_lower):
            # Try to find table name in question
            for db in schema_data.get("databases", []):
                for table in db.get("tables", []):
                    table_name = table.get("name", "").lower()
                    full_name = table.get("full_name", "").lower()
                    if table_name in question_lower or full_name in question_lower:
                        # Found the table
                        columns = table.get("columns", [])
                        col_lines = []
                        for col in columns:
                            flags = []
                            if col.get("is_primary_key"):
                                flags.append("PK")
                            if col.get("is_foreign_key"):
                                flags.append("FK")
                            if not col.get("is_nullable", True):
                                flags.append("NOT NULL")
                            flag_str = f" [{', '.join(flags)}]" if flags else ""
                            col_lines.append(f"  • {col['name']}: {col['data_type']}{flag_str}")

                        return {
                            "success": True,
                            "intent": "meta",
                            "answer": f"Table: {db['name']}.{table['full_name']}\n"
                                      f"Description: {table.get('description', 'N/A')}\n"
                                      f"Rows: ~{table.get('row_count_estimate', 'unknown'):,}\n"
                                      f"Columns ({len(columns)}):\n" + "\n".join(col_lines),
                            "sql": None,
                            "results": None
                        }

            # Table not found
            return {
                "success": True,
                "intent": "meta",
                "answer": "I couldn't identify the table you're asking about. "
                          "Please specify the table name. Available tables:\n" +
                          "\n".join(f"  • {t}" for t in schema_loader.get_table_names()[:20]),
                "sql": None,
                "results": None
            }

        # Count tables/databases/columns (visibility-aware)
        if re.search(r'\b(how many|count|number of)\b', question_lower):
            stats = schema_loader.get_stats(visible_only=True)
            return {
                "success": True,
                "intent": "meta",
                "answer": f"Database statistics:\n"
                          f"  • Databases: {stats.total_databases}\n"
                          f"  • Tables: {stats.total_tables}\n"
                          f"  • Columns: {stats.total_columns}\n"
                          f"  • Estimated prompt tokens: ~{stats.estimated_tokens:,}",
                "sql": None,
                "results": None
            }

        # General structure question - return full meta info (visibility-aware)
        return {
            "success": True,
            "intent": "meta",
            "answer": schema_loader.get_meta_info(visible_only=True),
            "sql": None,
            "results": None
        }

    def _validate_sql(self, sql: str) -> Tuple[bool, str]:
        """Validate SQL for safety."""
        sql_upper = sql.upper().strip()

        # Must be SELECT
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT statements are allowed"

        # Check for forbidden operations
        forbidden = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
                     'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE']
        for word in forbidden:
            if re.search(rf'\b{word}\b', sql_upper):
                return False, f"Forbidden operation: {word}"

        return True, "Valid"

    def _clean_sql(self, sql: str) -> str:
        """Clean SQL from LLM response."""
        sql = sql.strip()
        # Remove markdown code blocks
        sql = re.sub(r'^```sql\s*', '', sql, flags=re.IGNORECASE)
        sql = re.sub(r'^```\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        # Remove trailing semicolons (we'll add if needed)
        sql = sql.rstrip(';').strip()
        return sql + ';'

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse JSON response from LLM."""
        # Try to extract JSON from response
        try:
            # Try direct parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: treat as raw SQL if it looks like SQL
        if response.strip().upper().startswith('SELECT'):
            return {
                "intent": "data",
                "response": {
                    "sql": response.strip(),
                    "explanation": "Generated SQL query"
                }
            }

        raise ValueError(f"Could not parse LLM response: {response[:200]}")

    def _generate_sql(self, question: str, context: str = "") -> Dict:
        """Generate SQL using LLM with full schema."""
        user_prompt = USER_PROMPT_TEMPLATE.format(
            question=question,
            context=f"Conversation context: {context}" if context else ""
        )

        system_prompt = self._get_system_prompt()
        logger.info(f"[generate_sql] Sending schema ({len(system_prompt)} chars) + question to LLM")
        step_start = time.time()
        try:
            response = self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=2000,
                json_mode=True
            )
        except Exception as e:
            step_ms = int((time.time() - step_start) * 1000)
            logger.error(f"[generate_sql] LLM chat_completion FAILED after {step_ms}ms: {type(e).__name__}: {e}", exc_info=True)
            raise

        step_ms = int((time.time() - step_start) * 1000)
        logger.info(f"[generate_sql] LLM responded in {step_ms}ms | response_preview=\"{response[:200]}\"")

        parsed = self._parse_llm_response(response)
        logger.info(f"[generate_sql] Parsed intent={parsed.get('intent')} | has_sql={bool(parsed.get('response', {}).get('sql'))}")
        return parsed

    def _clean_sql_for_sqlite(self, sql: str) -> str:
        """Remove schema qualifiers (e.g. .public.) from SQL for SQLite compatibility."""
        # Replace db_name.public.table_name with db_name.table_name
        sql = re.sub(r'(\w+)\.public\.(\w+)', r'\1.\2', sql)
        # Replace db_name.dbo.table_name with db_name.table_name
        sql = re.sub(r'(\w+)\.dbo\.(\w+)', r'\1.\2', sql)
        return sql

    def _execute_sql(self, sql: str) -> Tuple[bool, Any, str]:
        """Execute SQL query using SQLite multi-db connection."""
        conn = None
        step_start = time.time()
        logger.info(f"[execute_sql] Executing: {sql[:200]}")
        try:
            # Clean SQL for SQLite compatibility
            sql = self._clean_sql_for_sqlite(sql)

            conn = get_multi_db_connection(visible_only=True)
            # Set busy timeout to avoid hanging on locked databases
            conn.execute(f"PRAGMA busy_timeout = {self.query_timeout * 1000}")

            cursor = conn.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            results = {
                "columns": columns,
                "rows": [dict(row) for row in rows],
                "row_count": len(rows)
            }
            step_ms = int((time.time() - step_start) * 1000)
            logger.info(f"[execute_sql] OK {step_ms}ms | {len(rows)} rows, {len(columns)} columns")
            return True, results, ""
        except Exception as e:
            step_ms = int((time.time() - step_start) * 1000)
            logger.error(f"[execute_sql] FAILED {step_ms}ms | error={e}")
            return False, None, str(e)
        finally:
            if conn:
                conn.close()

    def _correct_sql(self, question: str, failed_sql: str, error: str) -> str:
        """Attempt to correct failed SQL using detailed correction prompt."""
        logger.info(f"[correct_sql] Correcting failed SQL | error={error[:150]}")
        correction_prompt = SQL_CORRECTION_PROMPT.format(
            query=question,
            failed_sql=failed_sql,
            error_message=error,
            schemas=self.schema_loader.get_schema_text()
        )

        step_start = time.time()
        try:
            response = self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": correction_prompt}
                ],
                temperature=0.0,
                max_tokens=1000
            )
        except Exception as e:
            step_ms = int((time.time() - step_start) * 1000)
            logger.error(f"[correct_sql] LLM correction FAILED after {step_ms}ms: {type(e).__name__}: {e}", exc_info=True)
            raise

        step_ms = int((time.time() - step_start) * 1000)
        corrected = self._clean_sql(response)
        logger.info(f"[correct_sql] LLM corrected in {step_ms}ms | new_sql=\"{corrected[:150]}\"")
        return corrected

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
        # Remove trailing empty lines from summary
        clean_summary = "\n".join(summary_lines).rstrip()
        return clean_summary, suggestions[:3]

    # Threshold: if results exceed this, use stats-based summarization
    LARGE_RESULT_THRESHOLD = 50

    def _summarize_results(self, question: str, sql: str, results: Dict) -> tuple:
        """Generate natural language summary of results. Returns (summary, suggestions).

        For small results (<50 rows): sends actual rows to LLM (accurate for small sets).
        For large results (>=50 rows): computes stats from ALL rows server-side,
        sends only stats to LLM (accurate for large sets, no data leakage).
        """
        row_count = results["row_count"]
        all_rows = results["rows"]

        if row_count >= self.LARGE_RESULT_THRESHOLD:
            return self._summarize_with_stats(question, sql, all_rows, row_count)
        else:
            return self._summarize_with_rows(question, sql, all_rows, row_count)

    def _summarize_with_rows(self, question: str, sql: str, rows: List, row_count: int) -> tuple:
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

        logger.info(f"[summarize] Small result set ({row_count} rows) — sending {len(truncated_rows)} rows to LLM")

        summary_prompt = SQL_RESULT_SUMMARY_PROMPT.format(
            query=question,
            sql=sql,
            results=json.dumps(truncated_rows, default=str),
            row_count=row_count
        )

        return self._call_llm_for_summary(summary_prompt, "rows")

    def _summarize_with_stats(self, question: str, sql: str, rows: List, row_count: int) -> tuple:
        """Summarize large result sets using pre-computed statistics from ALL rows.

        No raw data rows are sent to the LLM — only aggregated statistics.
        """
        logger.info(f"[summarize] Large result set ({row_count} rows) — computing stats from ALL rows")

        column_stats, value_distributions = self._compute_result_stats(rows)

        # Include a small sample (5 rows) only for context on data format
        sample_rows = rows[:5]
        truncated_sample = []
        for row in sample_rows:
            truncated_row = {}
            for k, v in row.items():
                sv = str(v) if v is not None else ""
                truncated_row[k] = sv[:100] if len(sv) > 100 else v
            truncated_sample.append(truncated_row)

        sample_note = (
            f"Sample rows (5 of {row_count}, for format reference only — use the statistics above for your analysis):\n"
            f"{json.dumps(truncated_sample, default=str)}"
        )

        summary_prompt = SQL_RESULT_STATS_SUMMARY_PROMPT.format(
            query=question,
            sql=sql,
            row_count=row_count,
            column_stats=column_stats,
            value_distributions=value_distributions,
            sample_note=sample_note
        )

        return self._call_llm_for_summary(summary_prompt, "stats")

    def _compute_result_stats(self, rows: List[Dict]) -> Tuple[str, str]:
        """Compute comprehensive statistics from ALL result rows.

        Returns (column_stats_text, value_distributions_text) for the LLM prompt.
        """
        if not rows:
            return "No data", "No data"

        columns = list(rows[0].keys())
        stats_lines = []
        distribution_lines = []

        for col in columns:
            values = [row.get(col) for row in rows]
            non_null = [v for v in values if v is not None and str(v).strip() != ""]
            null_count = len(values) - len(non_null)

            # Determine column type
            numeric_values = []
            for v in non_null:
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    pass

            is_numeric = len(numeric_values) > len(non_null) * 0.8  # 80%+ numeric = numeric column

            if is_numeric and numeric_values:
                # Numeric column stats
                avg_val = sum(numeric_values) / len(numeric_values)
                min_val = min(numeric_values)
                max_val = max(numeric_values)
                # Format nicely
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
                # Text/categorical column stats
                distinct_count = len(set(str(v) for v in non_null))
                stats_lines.append(
                    f"  {col}: text | count={len(non_null)} | distinct={distinct_count}"
                    f"{f' | {null_count} nulls' if null_count else ''}"
                )

            # Value distribution for categorical columns (or numeric with few distinct values)
            str_values = [str(v) for v in non_null]
            distinct_vals = set(str_values)

            if 1 < len(distinct_vals) <= 50:
                # Show distribution — count each value, sorted by frequency
                from collections import Counter
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

        column_stats_text = "\n".join(stats_lines) if stats_lines else "No column stats available"
        distributions_text = "\n".join(distribution_lines) if distribution_lines else "No categorical distributions (all columns are high-cardinality)"

        logger.info(f"[summarize] Stats computed: {len(columns)} columns, "
                     f"{len(stats_lines)} stat lines, {len(distribution_lines)} distribution lines")

        return column_stats_text, distributions_text

    def _call_llm_for_summary(self, prompt: str, mode: str) -> tuple:
        """Call LLM with a summarization prompt. Returns (summary, suggestions)."""
        logger.info(f"[summarize] Prompt length: {len(prompt)} chars (mode={mode})")

        step_start = time.time()
        try:
            response = self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
        except Exception as e:
            step_ms = int((time.time() - step_start) * 1000)
            logger.error(f"[summarize] LLM summarization FAILED after {step_ms}ms: {type(e).__name__}: {e}", exc_info=True)
            raise

        step_ms = int((time.time() - step_start) * 1000)
        summary, suggestions = self._parse_suggestions(response)
        logger.info(f"[summarize] OK {step_ms}ms (mode={mode}) | summary_chars={len(summary)} | suggestions={len(suggestions)}")
        return summary, suggestions

    def _summarize_no_results(self, question: str, sql: str) -> tuple:
        """Generate a natural language explanation when a query returns zero rows.
        Returns (summary, suggestions)."""
        no_results_prompt = (
            f"The user asked: \"{question}\"\n\n"
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
        step_start = time.time()
        response = self.llm.chat_completion(
            messages=[{"role": "user", "content": no_results_prompt}],
            temperature=0.4,
            max_tokens=1000
        )
        step_ms = int((time.time() - step_start) * 1000)
        summary, suggestions = self._parse_suggestions(response)
        logger.info(f"[summarize_no_results] OK {step_ms}ms | summary_chars={len(summary)} | suggestions={len(suggestions)}")
        return summary, suggestions

    def refresh_schema(self, reload_loader: bool = True):
        """Refresh the schema loader data (e.g. after upload).

        Args:
            reload_loader: If True, also reload the schema loader from disk/DB.
                          Set to False if the loader was already reloaded externally.
        """
        if reload_loader:
            self.schema_loader.reload()

    def run(self, question: str, context: str = "") -> Dict:
        """Run the full SQL pipeline."""
        start_time = time.time()
        logger.info(f"[pipeline] START question=\"{question[:120]}\" context_len={len(context)}")

        # Step 1: Check for meta-questions (no LLM needed)
        if self._detect_meta_question(question):
            logger.info("[pipeline] Detected meta-question, answering directly (no LLM)")
            result = self._answer_meta_question(question)
            result["processing_time_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"[pipeline] DONE meta | {result['processing_time_ms']}ms")
            return result

        # Step 2: Generate SQL using LLM
        try:
            llm_response = self._generate_sql(question, context)
        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)
            logger.error(f"[pipeline] FAILED at generate_sql step after {elapsed}ms: {type(e).__name__}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to understand question: {str(e)}",
                "intent": "error",
                "sql": None,
                "results": None,
                "processing_time_ms": elapsed
            }

        intent = llm_response.get("intent", "data")
        response_data = llm_response.get("response", {})
        logger.info(f"[pipeline] LLM returned intent={intent}")

        # Handle ambiguous intent
        if intent == "ambiguous":
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"[pipeline] DONE ambiguous | {elapsed}ms")
            return {
                "success": True,
                "intent": "ambiguous",
                "clarification": response_data.get("clarification", "Could you please provide more details?"),
                "sql": None,
                "results": None,
                "processing_time_ms": elapsed
            }

        # Handle meta intent from LLM
        if intent == "meta":
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"[pipeline] DONE meta (from LLM) | {elapsed}ms")
            return {
                "success": True,
                "intent": "meta",
                "answer": response_data.get("answer", ""),
                "sql": None,
                "results": None,
                "processing_time_ms": elapsed
            }

        # Handle data intent - execute SQL
        sql = response_data.get("sql", "")
        if not sql:
            elapsed = int((time.time() - start_time) * 1000)
            logger.warning(f"[pipeline] No SQL in LLM response | {elapsed}ms")
            return {
                "success": False,
                "error": "No SQL generated",
                "intent": "data",
                "sql": None,
                "results": None,
                "processing_time_ms": elapsed
            }

        sql = self._clean_sql(sql)
        logger.info(f"[pipeline] Generated SQL: {sql[:200]}")

        # Validate SQL
        is_valid, validation_msg = self._validate_sql(sql)
        if not is_valid:
            elapsed = int((time.time() - start_time) * 1000)
            logger.warning(f"[pipeline] SQL validation failed: {validation_msg} | {elapsed}ms")
            return {
                "success": False,
                "error": f"Invalid SQL: {validation_msg}",
                "intent": "data",
                "sql": sql,
                "results": None,
                "processing_time_ms": elapsed
            }

        # Execute with retry loop
        last_error = ""
        for attempt in range(self.max_retries + 1):
            logger.info(f"[pipeline] Execute attempt {attempt + 1}/{self.max_retries + 1}")
            success, results, error = self._execute_sql(sql)

            if success:
                logger.info(f"[pipeline] SQL executed OK | {results['row_count']} rows")
                suggestions = []

                if results["row_count"] == 0:
                    # No data found — use LLM to generate a natural, context-aware response
                    logger.info("[pipeline] Zero rows returned, generating natural language response")
                    try:
                        summary, suggestions = self._summarize_no_results(question, sql)
                        if not summary or not summary.strip():
                            summary = (f"I looked through the database for your query but couldn't find any matching results. "
                                       f"This could mean the data doesn't exist yet, or the search criteria might need adjusting. "
                                       f"Could you try rephrasing or broadening your search?")
                    except Exception as e:
                        logger.warning(f"[pipeline] No-results summarization failed: {e}")
                        summary = (f"I couldn't find any data matching your question. "
                                   f"The specific criteria you mentioned may not have corresponding entries in the database. "
                                   f"Try adjusting your search terms or ask me what data is available.")
                else:
                    try:
                        summary, suggestions = self._summarize_results(question, sql, results)
                        # Guard against empty LLM summary
                        if not summary or not summary.strip():
                            summary = f"Query returned {results['row_count']} row(s)."
                            logger.warning("[pipeline] LLM returned empty summary, using fallback")
                    except Exception as e:
                        elapsed = int((time.time() - start_time) * 1000)
                        logger.error(f"[pipeline] Summarization failed after {elapsed}ms: {e}", exc_info=True)
                        summary = f"Query returned {results['row_count']} rows."

                elapsed = int((time.time() - start_time) * 1000)
                logger.info(f"[pipeline] DONE data success | attempts={attempt + 1} | {elapsed}ms")
                return {
                    "success": True,
                    "intent": "data",
                    "sql": sql,
                    "results": results,
                    "summary": summary,
                    "suggestions": suggestions,
                    "explanation": response_data.get("explanation", ""),
                    "attempts": attempt + 1,
                    "processing_time_ms": elapsed
                }

            # Attempt correction
            last_error = error
            if attempt < self.max_retries:
                logger.info(f"[pipeline] SQL failed, attempting correction (attempt {attempt + 1})")
                try:
                    sql = self._correct_sql(question, sql, error)
                except Exception as e:
                    logger.error(f"[pipeline] SQL correction LLM call failed: {e}", exc_info=True)
                    break
                is_valid, validation_msg = self._validate_sql(sql)
                if not is_valid:
                    logger.warning(f"[pipeline] Corrected SQL still invalid: {validation_msg}")
                    last_error = validation_msg

        elapsed = int((time.time() - start_time) * 1000)
        logger.error(f"[pipeline] FAILED after {self.max_retries + 1} attempts | last_error={last_error} | {elapsed}ms")
        return {
            "success": False,
            "error": f"Query failed after {self.max_retries + 1} attempts. Last error: {last_error}",
            "summary": ("I wasn't able to find an answer for that. "
                        "Could you try rephrasing your question or providing more details?"),
            "intent": "data",
            "sql": sql,
            "results": None,
            "processing_time_ms": elapsed
        }


# Singleton
_pipeline: Optional[SQLPipelineV2] = None


def get_sql_pipeline() -> SQLPipelineV2:
    """Get SQL pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = SQLPipelineV2()
    return _pipeline
