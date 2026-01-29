"""Prompt templates for all LLM operations."""

# ============================================================
# INTENT CLASSIFICATION
# ============================================================
INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an American Airlines crew management chatbot.

Classify the user's query into exactly one of these intents:
- DATA: Questions requiring database queries about crew data, flights, schedules, payroll, training records, compliance, policies, procedures, or any crew operations topic
- GENERAL: Greetings, chitchat, thank you, general questions not specific to crew operations

Conversation history (last 3 turns):
{conversation_history}

Current user query: {query}

Respond in JSON format:
{{
  "intent": "DATA" | "GENERAL",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation of why this intent was chosen",
  "follow_up_question": "question to ask user if confidence < 0.7 to clarify their intent, else null",
  "detected_entities": ["list of key entities detected like crew names, flight numbers, dates, etc."]
}}"""

# ============================================================
# QUERY REWRITING (for follow-up questions)
# ============================================================
QUERY_REWRITE_PROMPT = """You are a query rewriter. Your job is to rewrite follow-up questions into standalone questions.

Conversation history:
{history}

Current follow-up question: {query}

Rewrite this into a complete, standalone question that includes all necessary context from the conversation.
Only output the rewritten question, nothing else."""

# ============================================================
# SQL GENERATION
# ============================================================
SQL_GENERATION_PROMPT = """You are a SQL expert for an American Airlines crew management database system.
Generate a SQLite SELECT query to answer the user's question.

IMPORTANT DATABASE INFORMATION:
- There are 4 separate SQLite databases attached together: crew_management, flight_operations, hr_payroll, compliance_training
- You MUST ALWAYS prefix table names with the database name: db_name.table_name
  Example: crew_management.crew_members, hr_payroll.payroll_records
- Cross-database JOINs ARE supported. You can join tables across databases freely.
- All crew-related tables use employee_id (TEXT, e.g. 'AA-10001') as the common identifier.
  Use employee_id to JOIN crew data across databases.

Available schemas and tables:
{schema_descriptions}

RULES:
1. Only generate SELECT statements - no INSERT, UPDATE, DELETE, DROP, etc.
2. ALWAYS use db_name.table_name syntax (e.g. crew_management.crew_members, NOT just crew_members)
3. Add LIMIT 100 unless the user asks for a specific count or all records
4. Use meaningful column aliases for readability
5. For date comparisons, use SQLite date functions: date(), datetime(), strftime()
6. Use LIKE with % for partial text matching
7. Handle NULL values appropriately
8. For cross-database queries, JOIN on employee_id which is consistent across all databases

User question: {query}

Respond with ONLY the SQL query. No explanations, no markdown, just the raw SQL."""

SQL_GENERATION_WITH_CONTEXT_PROMPT = """You are a SQL expert for an American Airlines crew management database system.

Previous conversation context:
{conversation_context}

Available schemas:
{schema_descriptions}

Current question: {query}

Generate a SQLite SELECT query to answer the question.
Consider the conversation context for any referenced entities.

Rules:
1. Only SELECT statements
2. ALWAYS use db_name.table_name syntax (e.g. crew_management.crew_members)
3. Cross-database JOINs are supported - JOIN on employee_id across databases
4. Add LIMIT 100 unless counting
5. Use proper date functions for SQLite
6. No markdown, just raw SQL

SQL:"""

# ============================================================
# SQL SELF-CORRECTION
# ============================================================
SQL_CORRECTION_PROMPT = """The following SQL query failed. Please fix it.

Original question: {query}

Failed SQL:
{failed_sql}

Error message: {error_message}

Available schemas:
{schemas}

IMPORTANT: Always prefix table names with the database name (e.g. crew_management.crew_members, hr_payroll.payroll_records).
Cross-database JOINs are supported. Use employee_id to join crew data across databases.

Generate a corrected SQL query that will work.
Only output the corrected SQL, no explanations."""

# ============================================================
# SQL RESULT FORMATTING
# ============================================================
SQL_RESULT_SUMMARY_PROMPT = """You are a helpful assistant summarizing database query results for airline crew staff.

User's original question: {query}

SQL query executed:
{sql}

Query results (as JSON):
{results}

Number of rows returned: {row_count}

Provide a natural language summary of these results. Be concise but informative.
If the results are empty, explain what that means in context of the question.
Format any dates, times, and numbers nicely.
If there are many rows, summarize the key findings rather than listing everything."""

# ============================================================
# GENERAL CHAT
# ============================================================
GENERAL_CHAT_PROMPT = """You are a friendly assistant for American Airlines crew members.

Conversation history:
{history}

User message: {query}

Respond naturally and helpfully. If they're asking about crew policies or data,
suggest they ask a specific question about policies or their crew records.
Keep responses brief and professional."""

# ============================================================
# SCHEMA DESCRIPTION GENERATION
# ============================================================
SCHEMA_DESCRIPTION_PROMPT = """Generate a concise description of what this database table stores and how it relates to airline crew operations.

Database: {db_name}
Table: {table_name}

Columns:
{columns}

Sample data (3 rows):
{sample_data}

Write a 1-2 sentence description that will help match user questions to this table.
Focus on what kind of information it stores and when someone would query it.

Description:"""

# ============================================================
# CLARIFICATION PROMPTS
# ============================================================
CLARIFICATION_PROMPT = """The user's question is ambiguous. Generate a clarifying question.

User's question: {query}

Generate a brief, friendly clarifying question to determine if they want to look up specific data from the databases (e.g., crew records, flight schedules, training information, payroll data, compliance records).

Clarifying question:"""

# ============================================================
# VISUALIZATION SUGGESTION
# ============================================================
VISUALIZATION_PROMPT = """Based on these SQL query results, suggest the best visualization type.

Query: {query}
Columns: {columns}
Sample data: {sample_data}
Row count: {row_count}

Suggest ONE of these visualization types and explain briefly:
- bar_chart: For comparing categories
- line_chart: For trends over time
- pie_chart: For proportions (use sparingly, only if <7 categories)
- table: For detailed data
- metric: For single values or KPIs
- none: If visualization doesn't add value

Respond in JSON:
{{
  "chart_type": "bar_chart|line_chart|pie_chart|table|metric|none",
  "x_column": "column name for x-axis (if applicable)",
  "y_column": "column name for y-axis (if applicable)",
  "title": "suggested chart title",
  "reasoning": "brief explanation"
}}"""
