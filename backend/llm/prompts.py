"""All the prompt templates used for intent classification, SQL generation, summarization, etc."""

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
- Cross-database JOINs ARE fully supported. You can freely join tables across different databases.
- All crew-related tables use employee_id (TEXT) as the universal join key across ALL databases.

CRITICAL DATA VALUE REFERENCE:
- crew_roster.roster_month is TEXT with full month names: 'January', 'February', 'March', 'April', 'May', 'June', etc.
- crew_roster.roster_year is INTEGER: 2025
- crew_roster.roster_status values: 'Awarded', 'Reserve', 'Standby', 'Not Awarded', 'Training', 'Leave', 'Mixed'
- crew_roster.not_awarded_reason values: 'Seniority', 'Qualification Gap', 'Schedule Conflict', 'Base Mismatch', 'Medical Hold', 'Training Conflict', 'Visa Issue', 'Staffing Requirement', 'Bid Not Submitted', 'Pairing Unavailable', 'Rest Requirement', 'Disciplinary Action', 'Probation Period', 'Union Dispute', 'Crew Complement Full', 'Aircraft Type Mismatch', 'Insufficient Flight Hours', 'Administrative Error', 'Voluntary Withdrawal', 'FAA Restriction', 'Fatigue Risk Flag'
- crew_roster.duty_type values: 'Line Flying', 'Reserve', 'Standby', 'Training', 'Leave', 'Admin', 'Mixed'
- crew_members.crew_role values: 'Captain', 'First Officer', 'Senior First Officer', 'Flight Engineer', 'Purser', 'Senior Cabin Crew', 'Cabin Crew', 'Trainee'
- crew_members.status values: 'Active', 'On Leave', 'Suspended', 'Inactive', 'Retired'
- flights.flight_status values: 'Scheduled', 'Boarding', 'Departed', 'In Air', 'Landed', 'Arrived', 'Cancelled', 'Diverted', 'Delayed'
- leave_records.leave_type values: 'Annual Leave', 'Sick Leave', 'Emergency Leave', 'Training Leave'

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
9. When asking about crew names, ALWAYS include first_name and last_name from crew_management.crew_members
10. When the question mentions "unawarded" or "not awarded", filter crew_roster.roster_status = 'Not Awarded'
11. For multi-database questions, use JOINs across databases freely - they work perfectly via employee_id
12. Always include the crew_management.crew_members table when the user wants to see crew names/details

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

CRITICAL DATA VALUE REFERENCE:
- crew_roster.roster_month is TEXT: 'January', 'February', 'March', etc.
- crew_roster.roster_status values: 'Awarded', 'Reserve', 'Standby', 'Not Awarded', 'Training', 'Leave', 'Mixed'
- crew_members.crew_role values: 'Captain', 'First Officer', 'Purser', 'Senior Cabin Crew', 'Cabin Crew'
- All crew tables use employee_id (TEXT) as universal join key across databases

Rules:
1. Only SELECT statements
2. ALWAYS use db_name.table_name syntax (e.g. crew_management.crew_members)
3. Cross-database JOINs are fully supported - JOIN on employee_id across databases
4. Add LIMIT 100 unless counting
5. Use proper date functions for SQLite
6. No markdown, just raw SQL
7. Always include crew names (first_name, last_name) from crew_members when asking about people

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

IMPORTANT RULES FOR CORRECTION:
1. ALWAYS prefix table names with the database name (e.g. crew_management.crew_members, hr_payroll.payroll_records)
2. Cross-database JOINs are fully supported. Use employee_id to join crew data across databases.
3. If the error mentions "no such table", ensure you are using db_name.table_name syntax.
4. If the error mentions "no such column", check the schema above for exact column names.
5. crew_roster.roster_month is TEXT ('January', 'February', etc.), NOT numeric.
6. crew_roster.roster_status values: 'Awarded', 'Reserve', 'Standby', 'Not Awarded', 'Training', 'Leave', 'Mixed'
7. All cross-database JOINs should use employee_id as the join key.
8. When showing crew details, JOIN with crew_management.crew_members for names.

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

SUMMARY RULES:
1. Provide a clear, complete natural language summary of the results.
2. If the user asked about specific crew members (e.g., "who", "which crew", "list"), include EVERY person's full name (first_name + last_name) in your answer. Do not skip names or say "and others".
3. If there are additional relevant details (like role, reason, status), include them for each person.
4. If the results are empty, explain what that means in context of the question.
5. Format any dates, times, and numbers nicely.
6. If there are more than 20 rows, list the first 20 with names and mention the total count.
7. Group results logically (e.g., by reason, by role, by status) when it helps readability.
8. Use a numbered list or bullet points when listing crew members for clarity.

FOLLOW-UP SUGGESTIONS:
After your summary, add exactly 3 follow-up questions the user might want to ask next. These should be related to the current query results and naturally extend the analysis.

Format the follow-up suggestions on separate lines at the very end, each prefixed with "SUGGESTION:" like this:
SUGGESTION: What is the breakdown of crew by base location?
SUGGESTION: Show me the training completion rate for each role
SUGGESTION: Which crew members have expiring qualifications?"""

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
