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
- Multiple SQLite databases are attached together. The schemas below show which databases and tables are available.
- You MUST ALWAYS prefix table names with the database name: db_name.table_name
  Example: crew_management.crew_members, hr_payroll.payroll_records
- Cross-database JOINs ARE fully supported. You can freely join tables across different databases.
- Many tables use employee_id (TEXT) as a join key across databases. Check the schemas below for the actual column names in each table.

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
- combineddatalax.sheet1.EmployeeID is INTEGER (range: 46496-774459, 130 distinct employees)
- combineddatalax.sheet1.SequenceID is INTEGER with only 4 internal values: 801111, 801112, 801114, 801116
- combineddatalax.sheet1.SequenceNumber is INTEGER — this is the human-readable sequence number that users refer to (e.g., 3715, 4201, etc.)
- CRITICAL: When a user says "sequence 3715" or any sequence number NOT in the 800000+ range, ALWAYS use SequenceNumber (NOT SequenceID). SequenceID only has 4 internal values. Users almost always mean SequenceNumber.
- combineddatalax.sheet1.SequencePosition is INTEGER (values: 1, 3, 4, 5)
- combineddatalax.sheet1.LegalityContextsID is INTEGER (values: 1, 2, 3, 4, 9, 10)
- combineddatalax.sheet1.IsLegal is INTEGER (0=Not Legal, 1=Legal)
- combineddatalax.sheet1.LegalityPhaseID is INTEGER (values: 1, 3)
- combineddatalax.sheet1.QLARuleName is TEXT (e.g., '24X7REST(IL)', 'TOUCHFD(NC)', 'DBLSTBY(IL)', 'RSTREQ(IL)', 'SpkrQualCheck')
- combineddatalax.sheet1.BaseCD is TEXT (all values are 'LAX')

Available schemas and tables:
{schema_descriptions}

RULES:
1. Only generate SELECT statements - no INSERT, UPDATE, DELETE, DROP, etc.
2. ALWAYS use db_name.table_name syntax (e.g. crew_management.crew_members, NOT just crew_members)
3. Do NOT add LIMIT unless the user explicitly asks for a specific number of results (e.g., "top 10", "first 5"). Always return all matching rows so aggregations and summaries are accurate.
4. Use meaningful column aliases for readability
5. For date comparisons, use SQLite date functions: date(), datetime(), strftime()
6. Use LIKE with % for partial text matching
7. Handle NULL values appropriately
8. For cross-database queries, JOIN on common columns like employee_id across databases
9. When asking about people/crew, include name columns if available in the schemas provided
10. When the question mentions "unawarded" or "not awarded", filter crew_roster.roster_status = 'Not Awarded'
11. For multi-database questions, use JOINs across databases freely via shared columns
12. IMPORTANT: Search ALL provided schemas for the requested data. Do NOT assume data only exists in one database. If looking for an employee by ID, search across all tables that have an employee/ID column using UNION ALL if needed.
13. When choosing which table to query, carefully read the column names in the schemas. Pick the table whose columns best match what the user is asking for. For employee lookups, start from the table that has the most person-related columns (name, ID, role, status, etc.), not auxiliary/lookup tables.
14. Do NOT invent or guess table names or column names. Only use tables and columns that appear in the schemas provided below.

User question: {query}

Respond with ONLY the SQL query. No explanations, no markdown, just the raw SQL."""

SQL_GENERATION_WITH_CONTEXT_PROMPT = """You are a SQL expert for an American Airlines crew management database system.
Generate a SQLite SELECT query to answer the user's current question.

Previous conversation context (use ONLY to resolve pronouns like "that", "they", "those", or implicit references):
{conversation_context}

IMPORTANT DATABASE INFORMATION:
- Multiple SQLite databases are attached together. The schemas below show which databases and tables are available.
- You MUST ALWAYS prefix table names with the database name: db_name.table_name
  Example: crew_management.crew_members, hr_payroll.payroll_records
- Cross-database JOINs ARE fully supported. You can freely join tables across different databases.
- Many tables use employee_id (TEXT) as a join key across databases. Check the schemas below for the actual column names in each table.

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
- combineddatalax.sheet1.EmployeeID is INTEGER (range: 46496-774459, 130 distinct employees)
- combineddatalax.sheet1.SequenceID is INTEGER with only 4 internal values: 801111, 801112, 801114, 801116
- combineddatalax.sheet1.SequenceNumber is INTEGER — this is the human-readable sequence number that users refer to (e.g., 3715, 4201, etc.)
- CRITICAL: When a user says "sequence 3715" or any sequence number NOT in the 800000+ range, ALWAYS use SequenceNumber (NOT SequenceID). SequenceID only has 4 internal values. Users almost always mean SequenceNumber.
- combineddatalax.sheet1.SequencePosition is INTEGER (values: 1, 3, 4, 5)
- combineddatalax.sheet1.LegalityContextsID is INTEGER (values: 1, 2, 3, 4, 9, 10)
- combineddatalax.sheet1.IsLegal is INTEGER (0=Not Legal, 1=Legal)
- combineddatalax.sheet1.LegalityPhaseID is INTEGER (values: 1, 3)
- combineddatalax.sheet1.QLARuleName is TEXT (e.g., '24X7REST(IL)', 'TOUCHFD(NC)', 'DBLSTBY(IL)', 'RSTREQ(IL)', 'SpkrQualCheck')
- combineddatalax.sheet1.BaseCD is TEXT (all values are 'LAX')

Available schemas and tables:
{schema_descriptions}

RULES:
1. Only generate SELECT statements - no INSERT, UPDATE, DELETE, DROP, etc.
2. ALWAYS use db_name.table_name syntax (e.g. crew_management.crew_members, NOT just crew_members)
3. Do NOT add LIMIT unless the user explicitly asks for a specific number of results (e.g., "top 10", "first 5"). Always return all matching rows so aggregations and summaries are accurate.
4. Use meaningful column aliases for readability
5. For date comparisons, use SQLite date functions: date(), datetime(), strftime()
6. Use LIKE with % for partial text matching
7. Handle NULL values appropriately
8. For cross-database queries, JOIN on common columns like employee_id across databases
9. When asking about people/crew, include name columns if available in the schemas provided
10. When the question mentions "unawarded" or "not awarded", filter crew_roster.roster_status = 'Not Awarded'
11. For multi-database questions, use JOINs across databases freely via shared columns
12. IMPORTANT: Search ALL provided schemas for the requested data. Do NOT assume data only exists in one database. If looking for an employee by ID, search across all tables that have an employee/ID column using UNION ALL if needed.
13. When choosing which table to query, carefully read the column names in the schemas. Pick the table whose columns best match what the user is asking for. For employee lookups, start from the table that has the most person-related columns (name, ID, role, status, etc.), not auxiliary/lookup tables.
14. Do NOT invent or guess table names or column names. Only use tables and columns that appear in the schemas provided below.
15. Focus on the CURRENT question. Use conversation context only to resolve references like "that employee" or "those results", not to change the query strategy.

Current question: {query}

Respond with ONLY the SQL query. No explanations, no markdown, just the raw SQL."""

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

Query results (as JSON, may be a subset of total rows):
{results}

Number of rows returned: {row_count}

SUMMARY RULES:
1. ANSWER THE USER'S QUESTION DIRECTLY. Do not just describe what the data contains — explain what it means. If the user asked "why", provide the reasons. If they asked "who", list the names. If they asked "how many", give the count.
2. CONSOLIDATE REPETITIVE DATA. If multiple rows share the same employee/person but differ by date, time, sequence, or other dimension, do NOT list each row separately. Instead, summarize the patterns (e.g., "Employee 502370 was not legal for any of the 100 sequences due to: insufficient rest (45 sequences), exceeded duty hours (30 sequences), qualification gap (25 sequences)").
3. IDENTIFY UNIQUE REASONS/CATEGORIES. When data has repeated entries with different reason codes, statuses, or categories, group and count them. Present a breakdown (e.g., by reason, by status, by date).
4. If the user asked about specific crew members (e.g., "who", "which crew", "list"), include full names (first_name + last_name).
5. If the results are empty, explain what that means in context of the question.
6. Format any dates, times, and numbers nicely.
7. If listing many distinct people, list the first 20 with names and mention the total count.
8. Group results logically (e.g., by reason, by role, by status) when it helps readability.
9. Use bullet points or numbered lists for clarity.
10. Keep the summary concise but complete. A good summary answers the question in 2-5 sentences plus a breakdown if needed.

FOLLOW-UP SUGGESTIONS:
After your summary, add exactly 3 follow-up questions the user might want to ask next. These should be related to the current query results and naturally extend the analysis.

Format the follow-up suggestions on separate lines at the very end, each prefixed with "SUGGESTION:" like this:
SUGGESTION: What is the breakdown of crew by base location?
SUGGESTION: Show me the training completion rate for each role
SUGGESTION: Which crew members have expiring qualifications?"""

# ============================================================
# SQL RESULT FORMATTING (STATS-BASED for large result sets)
# ============================================================
SQL_RESULT_STATS_SUMMARY_PROMPT = """You are a helpful and insightful assistant summarizing database query results for airline crew staff.

User's original question: {query}

SQL query executed:
{sql}

Total rows returned: {row_count}

IMPORTANT: Instead of raw rows, you are given pre-computed statistics from ALL {row_count} rows. This ensures your analysis is accurate and complete — not based on a sample.

Column Statistics:
{column_stats}

Top Value Distributions:
{value_distributions}

{sample_note}

SUMMARY RULES:
1. ANSWER THE USER'S QUESTION DIRECTLY using the statistics provided. Be conversational and insightful, like a knowledgeable colleague explaining data findings.
2. USE THE STATISTICS to give ACCURATE numbers. If the stats show 4,000 employees in DFW, say exactly that — don't approximate or guess.
3. HIGHLIGHT KEY INSIGHTS — what stands out? Dominant categories, unusual patterns, concentrations, outliers mentioned in the stats.
4. PROVIDE CONTEXT — explain what the numbers mean in practical terms. "60% of crew are based in DFW, making it the largest hub by a significant margin" is better than just "DFW: 60%".
5. INCLUDE BREAKDOWNS when the distributions show meaningful categories. Use bullet points or numbered lists.
6. FORMAT numbers nicely — use commas for thousands, round percentages to 1 decimal, format dates readably.
7. If there are many categories, highlight the top 5-10 and summarize the rest as "and X others".
8. Keep the tone professional but friendly. Avoid technical jargon like "standard deviation" or "null count" — translate into plain English.
9. Keep the summary concise but complete — 3-6 sentences plus breakdown if needed.

FOLLOW-UP SUGGESTIONS:
After your summary, add exactly 3 follow-up questions the user might want to ask next. These should be related to the current results and naturally extend the analysis.

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

# ============================================================
# COLUMN DESCRIPTION GENERATION
# ============================================================
COLUMN_DESCRIPTION_PROMPT = """You are a database analyst. Given a table's column names, types, and sample data, generate a brief human-readable description for each column.

Database: {db_name}
Table: {table_name}

Columns and types:
{columns}

Sample data (up to 3 rows):
{sample_data}

For each column, infer its meaning from the column name, data type, and sample values.
If the column name is cryptic or abbreviated, do your best to guess what it represents.
If you truly cannot determine the meaning, use "Unknown - please describe manually".

Respond with ONLY a JSON object mapping each column name to its description. No markdown, no explanation.
Example: {{"emp_id": "Employee unique identifier", "lglru5485": "Legal rules code for crew scheduling"}}"""
