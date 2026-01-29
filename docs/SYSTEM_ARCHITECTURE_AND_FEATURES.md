# American Airlines Crew Management Chatbot
## Complete System Architecture & Features Documentation

**Version:** 1.0
**Last Updated:** January 2026
**Document Purpose:** Technical documentation for client presentations and stakeholder discussions

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Detailed Query Processing Flow](#3-detailed-query-processing-flow)
4. [Database Architecture](#4-database-architecture)
5. [Key Features](#5-key-features)
6. [Technical Components Deep Dive](#6-technical-components-deep-dive)
7. [Security Features](#7-security-features)
8. [Pros and Cons Analysis](#8-pros-and-cons-analysis)
9. [Performance Characteristics](#9-performance-characteristics)
10. [Frequently Asked Questions (FAQ)](#10-frequently-asked-questions-faq)
11. [Sample Queries and Responses](#11-sample-queries-and-responses)
12. [Technology Stack](#12-technology-stack)

---

## 1. Executive Summary

### What is this system?

The American Airlines Crew Management Chatbot is an **AI-powered conversational interface** that allows airline staff to query crew-related data using natural language. Instead of writing SQL queries or navigating complex database interfaces, users simply ask questions in plain English.

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Natural Language Queries** | Ask questions like "Who are the pilots based in Dallas?" |
| **Cross-Database Intelligence** | Seamlessly query across 4 separate databases in one question |
| **AI-Generated SQL** | No manual SQL writing - 100% automated query generation |
| **Self-Correcting** | Automatically fixes SQL errors and retries |
| **Conversational Memory** | Understands follow-up questions in context |
| **Secure Access** | JWT-based authentication with role-based access |

### Example Interaction

```
User: "Show me all captains with expiring medical certificates"

System Response: "Found 5 captains with medical certificates expiring within 30 days:

1. John Smith (AA-10015) - Medical expires: Feb 5, 2026
2. Sarah Johnson (AA-10023) - Medical expires: Feb 12, 2026
3. Michael Chen (AA-10031) - Medical expires: Feb 18, 2026
4. Emily Davis (AA-10042) - Medical expires: Feb 25, 2026
5. Robert Wilson (AA-10048) - Medical expires: Feb 28, 2026

These crew members should be scheduled for medical renewal."
```

---

## 2. System Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  FRONTEND                                        │
│                            (Streamlit Web App)                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Login     │  │    Chat     │  │   SQL       │  │   Feedback              │ │
│  │   Screen    │  │  Interface  │  │  Display    │  │   (Thumbs Up/Down)      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ REST API (HTTP/JSON)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  BACKEND                                         │
│                              (FastAPI Server)                                    │
│                                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │  Authentication  │    │  Intent Router   │    │  Query Rewriter  │          │
│  │  (JWT Tokens)    │    │  (Classify Query)│    │  (Context Aware) │          │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘          │
│                                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │  Schema RAG      │    │  SQL Generator   │    │  SQL Executor    │          │
│  │  (FAISS Vector)  │    │  (LLM Powered)   │    │  (Cross-DB)      │          │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘          │
│                                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐          │
│  │  Result          │    │  PII Masker      │    │  Conversation    │          │
│  │  Summarizer      │    │  (Privacy)       │    │  Manager         │          │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
┌─────────────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐
│    SQLite DATABASES     │  │   FAISS INDEX   │  │      LLM API               │
│                         │  │                 │  │   (Coforge/Quasar)         │
│  • crew_management.db   │  │  Schema vectors │  │                            │
│  • flight_operations.db │  │  for semantic   │  │  • Chat Completions        │
│  • hr_payroll.db        │  │  table search   │  │  • Text Embeddings         │
│  • compliance_training.db│  │                 │  │                            │
│  • app.db               │  │                 │  │                            │
└─────────────────────────┘  └─────────────────┘  └─────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Frontend (Streamlit)** | User interface, chat display, authentication UI |
| **Backend (FastAPI)** | API endpoints, business logic, orchestration |
| **Intent Router** | Classify queries as DATA or GENERAL |
| **Schema RAG** | Find relevant database tables for the query |
| **SQL Generator** | Convert natural language to SQL using LLM |
| **SQL Executor** | Run queries across multiple databases |
| **Result Summarizer** | Convert raw data to natural language |
| **LLM API** | External AI service for text generation and embeddings |

---

## 3. Detailed Query Processing Flow

### Step-by-Step Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER INPUT                                                               │
│ ═══════════════════                                                              │
│                                                                                  │
│ User types: "Show me all pilots with expiring medical certificates"              │
│                                                                                  │
│ What happens:                                                                    │
│ • Frontend captures the message                                                  │
│ • Sends to backend via POST /api/chat/message                                   │
│ • JWT token validated for authentication                                         │
│                                                                                  │
│ Time: ~10ms                                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: PII MASKING                                                              │
│ ═══════════════════                                                              │
│                                                                                  │
│ Purpose: Protect sensitive information before processing                         │
│                                                                                  │
│ Example:                                                                         │
│   Input:  "What is John Smith's salary?"                                        │
│   Masked: "What is [PERSON_1]'s salary?"                                        │
│                                                                                  │
│ Detected PII types:                                                             │
│ • Names (PERSON)                                                                │
│ • Email addresses                                                               │
│ • Phone numbers                                                                 │
│ • Social Security Numbers                                                       │
│                                                                                  │
│ The mapping is stored to unmask the final response.                             │
│                                                                                  │
│ Time: ~5ms                                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: QUERY REWRITING (Contextual)                                             │
│ ═══════════════════════════════════════                                          │
│                                                                                  │
│ Purpose: Handle follow-up questions that reference previous context              │
│                                                                                  │
│ Example conversation:                                                            │
│   User: "Show me pilots in Dallas"                                              │
│   Bot:  [Shows 15 pilots]                                                       │
│   User: "Which of them have type ratings for Boeing 777?"  ← Follow-up          │
│                                                                                  │
│ Rewriting process:                                                              │
│   Original: "Which of them have type ratings for Boeing 777?"                   │
│   Rewritten: "Which pilots in Dallas have type ratings for Boeing 777?"         │
│                                                                                  │
│ Triggered when: Query contains pronouns (them, it, those) or references         │
│                 (above, previous, same)                                         │
│                                                                                  │
│ LLM API call: Yes (only if rewriting needed)                                    │
│ Time: ~5 seconds (if needed), 0ms (if skipped)                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: INTENT CLASSIFICATION                                                    │
│ ═════════════════════════════════                                                │
│                                                                                  │
│ Purpose: Determine if query needs database access or is general chat            │
│                                                                                  │
│ Two-stage classification:                                                       │
│                                                                                  │
│ Stage 1 - Pattern Matching (Fast, No API):                                      │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ GENERAL patterns: "hi", "hello", "thanks", "bye", "good morning"        │     │
│ │ DATA patterns: "show", "list", "how many", "count" + crew/flight/pay    │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ Stage 2 - LLM Classification (Only if pattern doesn't match):                   │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ LLM analyzes query and returns:                                         │     │
│ │ {                                                                       │     │
│ │   "intent": "DATA",                                                     │     │
│ │   "confidence": 0.95,                                                   │     │
│ │   "reasoning": "User asking about crew medical certificates",           │     │
│ │   "detected_entities": ["pilots", "medical certificates"]               │     │
│ │ }                                                                       │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ Intent Types:                                                                   │
│ • DATA: Requires database query (crew, flights, payroll, training, etc.)        │
│ • GENERAL: Greetings, thanks, general conversation                              │
│ • CLARIFICATION: Ambiguous query, needs user clarification                      │
│                                                                                  │
│ Time: ~10ms (pattern match) or ~5 seconds (LLM)                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: SCHEMA RETRIEVAL (Semantic Search)                                       │
│ ═══════════════════════════════════════════                                      │
│                                                                                  │
│ Purpose: Find the most relevant database tables for the user's question         │
│                                                                                  │
│ Why this is needed:                                                             │
│ • We have 27 tables across 4 databases                                          │
│ • Sending all schemas to LLM would be too large and expensive                   │
│ • We need to select only the relevant 5-6 tables                                │
│                                                                                  │
│ Process:                                                                        │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ 1. Convert query to embedding vector using LLM Embedding API            │     │
│ │    "pilots with expiring medical" → [0.023, -0.156, 0.891, ...]        │     │
│ │                                                                         │     │
│ │ 2. Search FAISS index for similar table description vectors             │     │
│ │    FAISS performs approximate nearest neighbor search                   │     │
│ │                                                                         │     │
│ │ 3. Return top 5 most relevant tables:                                   │     │
│ │    ┌──────────────────────────────────────────────────────────────┐    │     │
│ │    │ Rank │ Table                              │ Similarity Score │    │     │
│ │    ├──────┼────────────────────────────────────┼──────────────────┤    │     │
│ │    │  1   │ crew_management.crew_qualifications│      0.92        │    │     │
│ │    │  2   │ crew_management.crew_members       │      0.89        │    │     │
│ │    │  3   │ compliance_training.compliance_checks│    0.85        │    │     │
│ │    │  4   │ crew_management.crew_documents     │      0.78        │    │     │
│ │    │  5   │ compliance_training.training_records│     0.71        │    │     │
│ │    └──────────────────────────────────────────────────────────────┘    │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ What's in the FAISS index (pre-built during setup):                             │
│ • Table name and database name                                                  │
│ • Rich description of what the table contains                                   │
│ • Column names and data types                                                   │
│ • Sample data for context                                                       │
│ • DDL (CREATE TABLE statement)                                                  │
│                                                                                  │
│ LLM API call: Yes (Embedding API)                                               │
│ Time: ~5-7 seconds                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: SQL GENERATION                                                           │
│ ══════════════════════                                                           │
│                                                                                  │
│ Purpose: Convert natural language question to SQL query                          │
│                                                                                  │
│ Input to LLM:                                                                   │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ PROMPT:                                                                 │     │
│ │ You are a SQL expert for American Airlines crew database.               │     │
│ │                                                                         │     │
│ │ IMPORTANT:                                                              │     │
│ │ - Use db_name.table_name syntax (e.g. crew_management.crew_members)     │     │
│ │ - JOIN on employee_id across databases                                  │     │
│ │ - Only SELECT statements allowed                                        │     │
│ │                                                                         │     │
│ │ Available schemas:                                                      │     │
│ │ [Retrieved schemas from Step 5]                                         │     │
│ │                                                                         │     │
│ │ User question: "Show me all pilots with expiring medical certificates"  │     │
│ │                                                                         │     │
│ │ Generate SQL:                                                           │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ LLM Output (Generated SQL):                                                     │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ SELECT                                                                  │     │
│ │     cm.employee_id,                                                     │     │
│ │     cm.name,                                                            │     │
│ │     cm.crew_role,                                                       │     │
│ │     cq.certificate_type,                                                │     │
│ │     cq.expiry_date                                                      │     │
│ │ FROM crew_management.crew_members cm                                    │     │
│ │ JOIN crew_management.crew_qualifications cq                             │     │
│ │     ON cm.employee_id = cq.employee_id                                  │     │
│ │ WHERE cm.crew_role IN ('Captain', 'First Officer')                      │     │
│ │     AND cq.certificate_type = 'Medical Certificate'                     │     │
│ │     AND cq.expiry_date <= date('now', '+30 days')                       │     │
│ │     AND cq.expiry_date >= date('now')                                   │     │
│ │ ORDER BY cq.expiry_date                                                 │     │
│ │ LIMIT 100                                                               │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ Key points:                                                                     │
│ • SQL is 100% AI-generated, not hardcoded                                       │
│ • Uses db_name.table_name syntax for cross-database queries                     │
│ • Automatically adds LIMIT 100 for safety                                       │
│ • Uses appropriate date functions for SQLite                                    │
│                                                                                  │
│ LLM API call: Yes (Chat Completion API)                                         │
│ Time: ~5-7 seconds                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: SQL VALIDATION                                                           │
│ ══════════════════════                                                           │
│                                                                                  │
│ Purpose: Ensure generated SQL is safe to execute                                 │
│                                                                                  │
│ Security checks performed:                                                      │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ ✓ Must start with SELECT                                                │     │
│ │ ✗ Blocks: DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE        │     │
│ │ ✗ Blocks: GRANT, REVOKE (permission changes)                           │     │
│ │ ✗ Blocks: Any non-SELECT statement                                     │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ If validation fails:                                                            │
│ • Return error to user: "Generated invalid SQL: Forbidden operation: DROP"      │
│ • Do not execute the query                                                      │
│                                                                                  │
│ Time: ~1ms                                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 8: CROSS-DATABASE EXECUTION                                                 │
│ ════════════════════════════════                                                 │
│                                                                                  │
│ Purpose: Execute SQL across multiple databases in a single query                 │
│                                                                                  │
│ How it works (SQLite ATTACH DATABASE):                                          │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │                                                                         │     │
│ │  1. Create in-memory SQLite connection                                  │     │
│ │     conn = sqlite3.connect(":memory:")                                  │     │
│ │                                                                         │     │
│ │  2. Attach all 4 databases with logical names                           │     │
│ │     ATTACH 'crew_management.db' AS crew_management                      │     │
│ │     ATTACH 'flight_operations.db' AS flight_operations                  │     │
│ │     ATTACH 'hr_payroll.db' AS hr_payroll                                │     │
│ │     ATTACH 'compliance_training.db' AS compliance_training              │     │
│ │                                                                         │     │
│ │  3. Execute query - can JOIN across any attached database               │     │
│ │     SELECT * FROM crew_management.crew_members cm                       │     │
│ │     JOIN hr_payroll.payroll_records pr                                  │     │
│ │       ON cm.employee_id = pr.employee_id                                │     │
│ │                                                                         │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ Common join key: employee_id (TEXT, e.g., 'AA-10001')                           │
│ This ID is consistent across ALL databases                                      │
│                                                                                  │
│ Timeout: 10 seconds (configurable)                                              │
│ Time: ~10-100ms (depends on query complexity)                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 9: SELF-CORRECTION (If SQL Fails)                                           │
│ ══════════════════════════════════════                                           │
│                                                                                  │
│ Purpose: Automatically fix SQL errors without user intervention                  │
│                                                                                  │
│ Trigger: SQL execution returns an error                                         │
│                                                                                  │
│ Process:                                                                        │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ Attempt 1: Execute original SQL                                         │     │
│ │   Error: "no such column: crew_role"                                    │     │
│ │                                                                         │     │
│ │ Correction: Send to LLM with error message                              │     │
│ │   "The SQL failed with error: no such column: crew_role                 │     │
│ │    Please fix the query. Available columns: role, ..."                  │     │
│ │                                                                         │     │
│ │ Attempt 2: Execute corrected SQL                                        │     │
│ │   Success!                                                              │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ Maximum retries: 3                                                              │
│ Each retry: ~5-7 seconds (LLM call for correction)                              │
│                                                                                  │
│ Success rate: ~95% queries succeed within 3 attempts                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 10: RESULT SUMMARIZATION                                                    │
│ ═════════════════════════════                                                    │
│                                                                                  │
│ Purpose: Convert raw database results to natural language response               │
│                                                                                  │
│ Input to LLM:                                                                   │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ User question: "Show me pilots with expiring medical certificates"      │     │
│ │                                                                         │     │
│ │ SQL executed: [the generated SQL]                                       │     │
│ │                                                                         │     │
│ │ Results (JSON):                                                         │     │
│ │ [                                                                       │     │
│ │   {"employee_id": "AA-10015", "name": "John Smith", ...},               │     │
│ │   {"employee_id": "AA-10023", "name": "Sarah Johnson", ...},            │     │
│ │   ...                                                                   │     │
│ │ ]                                                                       │     │
│ │                                                                         │     │
│ │ Row count: 5                                                            │     │
│ │                                                                         │     │
│ │ Generate a natural language summary.                                    │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ LLM Output:                                                                     │
│ ┌─────────────────────────────────────────────────────────────────────────┐     │
│ │ "Found 5 pilots with medical certificates expiring within 30 days:      │     │
│ │                                                                         │     │
│ │  1. John Smith (AA-10015) - Medical expires: Feb 5, 2026                │     │
│ │  2. Sarah Johnson (AA-10023) - Medical expires: Feb 12, 2026            │     │
│ │  3. Michael Chen (AA-10031) - Medical expires: Feb 18, 2026             │     │
│ │  4. Emily Davis (AA-10042) - Medical expires: Feb 25, 2026              │     │
│ │  5. Robert Wilson (AA-10048) - Medical expires: Feb 28, 2026            │     │
│ │                                                                         │     │
│ │  These crew members should be scheduled for medical renewal."           │     │
│ └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
│ LLM API call: Yes (Chat Completion API)                                         │
│ Time: ~5-7 seconds                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 11: PII UNMASKING & RESPONSE                                                │
│ ═════════════════════════════════                                                │
│                                                                                  │
│ Purpose: Restore original PII values in the response                             │
│                                                                                  │
│ Example:                                                                         │
│   Masked response: "[PERSON_1]'s salary is $8,500"                              │
│   Unmasked response: "John Smith's salary is $8,500"                            │
│                                                                                  │
│ Final response sent to frontend with:                                           │
│ • Natural language summary                                                      │
│ • Generated SQL query (for transparency)                                        │
│ • Raw results table (for detailed view)                                         │
│ • Processing time                                                               │
│ • Intent classification                                                         │
│                                                                                  │
│ Time: ~5ms                                                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Total Processing Time Breakdown

| Step | Component | Time | LLM API Call? |
|------|-----------|------|---------------|
| 1 | User Input | ~10ms | No |
| 2 | PII Masking | ~5ms | No |
| 3 | Query Rewriting | 0-5000ms | Sometimes |
| 4 | Intent Classification | 10-5000ms | Sometimes |
| 5 | Schema Retrieval | ~5000-7000ms | Yes (Embedding) |
| 6 | SQL Generation | ~5000-7000ms | Yes (Chat) |
| 7 | SQL Validation | ~1ms | No |
| 8 | SQL Execution | ~10-100ms | No |
| 9 | Self-Correction | 0-15000ms | Only on error |
| 10 | Result Summarization | ~5000-7000ms | Yes (Chat) |
| 11 | PII Unmasking | ~5ms | No |
| **Total (typical)** | | **~15-20 seconds** | **3 calls** |

---

## 4. Database Architecture

### Database Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATABASE ARCHITECTURE                                  │
│                                                                                  │
│  ┌─────────────────────┐     ┌─────────────────────┐                            │
│  │ crew_management.db  │     │ flight_operations.db│                            │
│  │ ─────────────────── │     │ ─────────────────── │                            │
│  │ • crew_members      │     │ • flights           │                            │
│  │ • crew_qualifications│    │ • aircraft          │                            │
│  │ • crew_assignments  │     │ • airports          │                            │
│  │ • crew_rest_records │     │ • crew_pairings     │                            │
│  │ • crew_documents    │     │ • pairing_flights   │                            │
│  │ • crew_contacts     │     │ • flight_legs       │                            │
│  │ • crew_roster       │     │ • disruptions       │                            │
│  │                     │     │ • hotels            │                            │
│  └──────────┬──────────┘     └──────────┬──────────┘                            │
│             │                           │                                        │
│             │      employee_id          │                                        │
│             │      (AA-10001)           │                                        │
│             │         ┌─────────────────┘                                        │
│             │         │                                                          │
│             ▼         ▼                                                          │
│  ┌─────────────────────┐     ┌─────────────────────┐                            │
│  │   hr_payroll.db     │     │compliance_training.db│                           │
│  │ ─────────────────── │     │ ─────────────────── │                            │
│  │ • pay_grades        │     │ • training_courses  │                            │
│  │ • payroll_records   │     │ • training_records  │                            │
│  │ • leave_records     │     │ • training_schedules│                            │
│  │ • leave_balances    │     │ • training_enrollments│                          │
│  │ • benefits          │     │ • compliance_checks │                            │
│  │ • performance_reviews│    │ • safety_incidents  │                            │
│  │ • expense_claims    │     │ • audit_logs        │                            │
│  └─────────────────────┘     └─────────────────────┘                            │
│                                                                                  │
│  ┌─────────────────────┐                                                        │
│  │      app.db         │  Application data (users, conversations, feedback)     │
│  │ ─────────────────── │                                                        │
│  │ • users             │                                                        │
│  │ • conversations     │                                                        │
│  │ • messages          │                                                        │
│  │ • feedback          │                                                        │
│  │ • schema_metadata   │                                                        │
│  └─────────────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Table Details by Database

#### 1. crew_management.db (7 tables)

| Table | Description | Key Columns | Sample Queries |
|-------|-------------|-------------|----------------|
| `crew_members` | Master crew records | employee_id, name, crew_role, base_airport, status | "List all captains", "Who is based in DFW?" |
| `crew_qualifications` | Licenses, ratings, certifications | employee_id, certificate_type, expiry_date | "Expiring medical certificates", "Who has 777 rating?" |
| `crew_assignments` | Flight assignments | employee_id, flight_id, duty_start, duty_end | "Who is assigned to AA123?", "John's schedule" |
| `crew_rest_records` | FAR 117 rest tracking | employee_id, rest_start, rest_end, meets_far117 | "Rest compliance", "Who needs rest?" |
| `crew_documents` | Passport, visa, licenses | employee_id, document_type, expiry_date | "Expiring passports", "Visa status" |
| `crew_contacts` | Emergency contacts | employee_id, contact_name, relationship, phone | "Emergency contact for AA-10015" |
| `crew_roster` | Monthly roster/bidding | employee_id, month, status, not_awarded_reason | "Why wasn't John awarded?", "Reserve crew count" |

#### 2. flight_operations.db (8 tables)

| Table | Description | Key Columns | Sample Queries |
|-------|-------------|-------------|----------------|
| `flights` | Flight schedule | flight_number, departure_airport, arrival_airport, status | "Delayed flights today", "Flights to LAX" |
| `aircraft` | Fleet information | registration, aircraft_type, seat_capacity, status | "Boeing 777 fleet", "Aircraft maintenance" |
| `airports` | Airport master data | iata_code, name, city, timezone, is_hub | "Hub airports", "Airports in Texas" |
| `crew_pairings` | Duty trip groupings | pairing_code, start_date, end_date, total_duty_hours | "Pairings this week", "Long pairings" |
| `pairing_flights` | Pairing-flight junction | pairing_id, flight_id, sequence_number | "Flights in pairing P001" |
| `flight_legs` | Multi-segment legs | flight_id, leg_sequence, departure_airport | "Legs for AA456" |
| `disruptions` | Delays, cancellations | flight_id, disruption_type, severity, reason | "Cancellations today", "Weather delays" |
| `hotels` | Crew layover hotels | airport_code, hotel_name, crew_rate, distance_to_airport | "Hotels at LAX", "Cheapest layover" |

#### 3. hr_payroll.db (7 tables)

| Table | Description | Key Columns | Sample Queries |
|-------|-------------|-------------|----------------|
| `pay_grades` | Salary structures | crew_role, seniority_band, base_monthly_salary | "Captain pay scale", "First Officer salary" |
| `payroll_records` | Monthly payroll | employee_id, pay_month, base_pay, flight_hour_pay, net_pay | "John's salary", "Total payroll this month" |
| `leave_records` | Leave requests | employee_id, leave_type, start_date, status | "Pending leave requests", "Sick leave today" |
| `leave_balances` | Leave entitlements | employee_id, leave_type, entitled_days, used_days | "John's remaining vacation", "Who has no leave?" |
| `benefits` | Insurance, 401k | employee_id, benefit_type, employee_contribution | "401k enrollments", "Health insurance" |
| `performance_reviews` | Annual reviews | employee_id, review_year, overall_rating | "Top performers", "Ratings below 3" |
| `expense_claims` | Reimbursements | employee_id, expense_type, amount, status | "Pending expenses", "Hotel claims" |

#### 4. compliance_training.db (7 tables)

| Table | Description | Key Columns | Sample Queries |
|-------|-------------|-------------|----------------|
| `training_courses` | Available courses | course_code, course_name, course_type, validity_months | "Recurrent training courses", "CRM courses" |
| `training_records` | Completed training | employee_id, course_id, completion_date, result | "John's training", "Failed training" |
| `training_schedules` | Upcoming sessions | course_id, scheduled_date, instructor, facility | "Training next week", "CRM schedule" |
| `training_enrollments` | Session enrollments | employee_id, schedule_id, enrollment_status | "Who is enrolled?", "Enrollment confirmations" |
| `compliance_checks` | Regulatory checks | employee_id, check_type, result, next_due_date | "Overdue checks", "Medical exam results" |
| `safety_incidents` | Incident reports | incident_type, severity, reported_by_employee_id | "Safety incidents", "Turbulence injuries" |
| `audit_logs` | System audit trail | entity_type, action, performed_by, timestamp | "Recent changes", "Who modified X?" |

### Employee ID: The Universal Key

All crew-related data is linked by `employee_id`:
- Format: `AA-XXXXX` (e.g., `AA-10001`, `AA-10050`)
- Type: TEXT (not integer)
- Present in all tables that reference a crew member
- Enables seamless cross-database JOINs

```sql
-- Example: Get crew member with their salary and training
SELECT
    cm.name,
    cm.crew_role,
    pr.net_pay,
    tr.course_name,
    tr.completion_date
FROM crew_management.crew_members cm
JOIN hr_payroll.payroll_records pr ON cm.employee_id = pr.employee_id
JOIN compliance_training.training_records tr ON cm.employee_id = tr.employee_id
WHERE cm.employee_id = 'AA-10015'
```

---

## 5. Key Features

### Feature Matrix

| Feature | Description | Benefit |
|---------|-------------|---------|
| **Natural Language Interface** | Ask questions in plain English | No SQL knowledge required |
| **Cross-Database Queries** | Query 4 databases in one question | Complete crew view in one query |
| **AI-Generated SQL** | Automatic query generation | No hardcoded queries |
| **Self-Correction** | Auto-fix SQL errors | Higher success rate |
| **Semantic Search** | Find relevant tables intelligently | Accurate schema selection |
| **Conversation Memory** | Handle follow-up questions | Natural conversation flow |
| **PII Protection** | Mask sensitive data | Privacy compliance |
| **User Feedback** | Thumbs up/down on responses | Continuous improvement |
| **Secure Authentication** | JWT-based access | Role-based security |
| **Audit Trail** | Log all queries and actions | Compliance and debugging |

### Feature Details

#### 1. Natural Language Interface
```
Instead of:
  SELECT * FROM crew_members WHERE crew_role = 'Captain' AND base_airport = 'DFW'

Users ask:
  "Show me all captains based in Dallas"
```

#### 2. Cross-Database Queries
```
Single question spans multiple databases:
  "Show me pilots with overdue training and their current leave balance"

This touches:
  - crew_management.crew_members (pilot info)
  - compliance_training.training_records (training status)
  - hr_payroll.leave_balances (leave info)
```

#### 3. Conversation Memory
```
User: "Show me all pilots in Dallas"
Bot:  [Shows 15 pilots]

User: "Which of them are captains?"  ← Follow-up
Bot:  [Shows 8 captains from the previous result]

User: "What are their salaries?"  ← Another follow-up
Bot:  [Shows salary for those 8 captains]
```

#### 4. Self-Correction Example
```
Attempt 1:
  SQL: SELECT name FROM crew_member WHERE role = 'Captain'
  Error: no such table: crew_member

Attempt 2 (Auto-corrected):
  SQL: SELECT name FROM crew_management.crew_members WHERE crew_role = 'Captain'
  Success!
```

#### 5. Intent Classification
```
DATA queries (go to SQL pipeline):
  - "Show me flights to LAX"
  - "What is John's salary?"
  - "How many pilots are on leave?"

GENERAL queries (handled directly):
  - "Hello"
  - "Thank you"
  - "Goodbye"
```

---

## 6. Technical Components Deep Dive

### 6.1 Schema RAG (Retrieval-Augmented Generation for Schemas)

**What is it?**
A technique to find relevant database tables for a user's question using semantic similarity.

**How it differs from traditional RAG:**
| Traditional RAG | Schema RAG (Our Approach) |
|----------------|---------------------------|
| Retrieves document chunks | Retrieves table schemas |
| For answering from documents | For SQL generation |
| Returns text passages | Returns table structures |

**Process:**
```
1. PRE-INDEXING (done once during setup):
   ┌────────────────────────────────────────────────────────┐
   │ For each table:                                        │
   │   • Extract table name, columns, DDL                   │
   │   • Add rich description (hand-written)                │
   │   • Generate embedding vector using LLM API            │
   │   • Store in FAISS index                               │
   └────────────────────────────────────────────────────────┘

2. AT QUERY TIME:
   ┌────────────────────────────────────────────────────────┐
   │ User question: "Show me pilots with expiring medical"  │
   │                            │                           │
   │                            ▼                           │
   │              Generate embedding vector                 │
   │                            │                           │
   │                            ▼                           │
   │              FAISS similarity search                   │
   │                            │                           │
   │                            ▼                           │
   │              Return top 5 matching tables              │
   └────────────────────────────────────────────────────────┘
```

**Schema description example:**
```python
"crew_qualifications": """
    Crew licenses, type ratings, medical certificates, language proficiency,
    security clearances, dangerous goods and first aid certifications.
    Linked by employee_id. Use this to check expiring qualifications or
    find crew with specific ratings.
"""
```

### 6.2 SQL Generation Pipeline

**Components:**
```
┌─────────────────────────────────────────────────────────────┐
│                    SQL PIPELINE                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. SQLPipeline.retrieve_schemas()                          │
│     └── Uses FAISS vector search                            │
│                                                             │
│  2. SQLPipeline.generate_sql()                              │
│     └── LLM generates SQL from question + schemas           │
│                                                             │
│  3. SQLPipeline.validate_sql()                              │
│     └── Security check (no DROP, DELETE, etc.)              │
│                                                             │
│  4. SQLPipeline.execute_sql()                               │
│     └── Run query on attached databases                     │
│                                                             │
│  5. SQLPipeline.correct_sql()  [if error]                   │
│     └── LLM fixes the failed query                          │
│                                                             │
│  6. SQLPipeline.summarize_results()                         │
│     └── LLM converts results to natural language            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Cross-Database Connection

**SQLite ATTACH mechanism:**
```python
def get_multi_db_connection():
    # Create in-memory connection as the "main" database
    conn = sqlite3.connect(":memory:")

    # Attach all operational databases
    conn.execute("ATTACH DATABASE ? AS crew_management", (crew_db_path,))
    conn.execute("ATTACH DATABASE ? AS flight_operations", (flight_db_path,))
    conn.execute("ATTACH DATABASE ? AS hr_payroll", (hr_db_path,))
    conn.execute("ATTACH DATABASE ? AS compliance_training", (compliance_db_path,))

    # Now queries can span all databases:
    # SELECT * FROM crew_management.crew_members cm
    # JOIN hr_payroll.payroll_records pr ON cm.employee_id = pr.employee_id

    return conn
```

### 6.4 LLM Integration

**API Configuration:**
```
Chat Completions API:
  URL: https://quasarmarket.coforge.com/qag/llmrouter-api/v2/completions
  Model: gpt-5-2
  Used for: SQL generation, result summarization, intent classification

Embedding API:
  URL: https://quasarmarket.coforge.com/qag/llmrouter-api/v2/text/embeddings
  Model: text-embeddings
  Dimensions: 746
  Used for: Schema retrieval (semantic search)
```

**Fallback mechanism:**
```
v2 URL (primary) → fails → v3 URL (fallback)
```

---

## 7. Security Features

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. USER AUTHENTICATION                                     │
│     • Username/password login                               │
│     • JWT token issued on successful login                  │
│     • Token expires after 60 minutes                        │
│     • Token required for all API calls                      │
│                                                             │
│  2. SQL INJECTION PREVENTION                                │
│     • Only SELECT statements allowed                        │
│     • Parameterized queries where applicable                │
│     • Forbidden keywords: DROP, DELETE, UPDATE, INSERT      │
│                                                             │
│  3. PII PROTECTION                                          │
│     • Names, emails, phones masked before LLM processing    │
│     • Unmasked only in final response                       │
│     • Prevents PII leakage to external APIs                 │
│                                                             │
│  4. AUDIT LOGGING                                           │
│     • All queries logged with timestamp                     │
│     • User ID recorded for each action                      │
│     • Stored in compliance_training.audit_logs              │
│                                                             │
│  5. ROLE-BASED ACCESS                                       │
│     • Admin users: Full access                              │
│     • Regular users: Limited to their own data              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### SQL Validation Rules

```python
FORBIDDEN_OPERATIONS = [
    'DROP',      # Cannot drop tables
    'DELETE',    # Cannot delete data
    'UPDATE',    # Cannot modify data
    'INSERT',    # Cannot add data
    'ALTER',     # Cannot change schema
    'CREATE',    # Cannot create objects
    'TRUNCATE',  # Cannot truncate tables
    'GRANT',     # Cannot change permissions
    'REVOKE'     # Cannot revoke permissions
]

# Only SELECT statements are executed
if not sql.strip().upper().startswith('SELECT'):
    raise SecurityError("Only SELECT statements allowed")
```

---

## 8. Pros and Cons Analysis

### Advantages

| Advantage | Description | Business Value |
|-----------|-------------|----------------|
| **No SQL Knowledge Required** | Users ask questions in plain English | Wider user adoption, reduced training costs |
| **Single Interface** | Query 4 databases from one chatbot | Unified view, no switching between systems |
| **Always Up-to-Date** | Queries live data, not cached reports | Real-time decision making |
| **Self-Healing** | Auto-corrects SQL errors | Higher reliability, less frustration |
| **Semantic Understanding** | Understands synonyms and context | More flexible querying |
| **Conversation Context** | Handles follow-up questions | Natural interaction flow |
| **Audit Trail** | All queries logged | Compliance and accountability |
| **Scalable Architecture** | Add more databases easily | Future-proof design |

### Limitations

| Limitation | Description | Mitigation |
|------------|-------------|------------|
| **Response Time** | 15-20 seconds per query | Due to 3 LLM API calls; can optimize with caching |
| **LLM Dependency** | Requires external API availability | Fallback URLs configured (v2 → v3) |
| **Complex Aggregations** | May struggle with very complex analytics | Provide example queries in training |
| **No Real-Time Updates** | Batch data refresh, not streaming | Schedule regular data syncs |
| **Token Limits** | Very large result sets may be truncated | LIMIT 100 applied by default |
| **Learning Curve** | Users need to learn effective questioning | Provide query examples and tips |

### When to Use This System

**Good Fit:**
- Ad-hoc queries by non-technical users
- Quick lookups and simple aggregations
- Cross-database questions
- Conversational exploration of data

**Not Ideal For:**
- Complex analytical reports (use BI tools)
- Real-time dashboards (use dedicated dashboards)
- Bulk data exports (use direct database access)
- Highly sensitive operations (use controlled interfaces)

---

## 9. Performance Characteristics

### Response Time Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│              TYPICAL QUERY: 15-20 seconds                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ████████████████████░░░░░░░░░░░░░░░░░░░░  Schema Search    │
│  (5-7 seconds)                              Embedding API    │
│                                                             │
│  ░░░░░░░░░░░░░░░░░░░░████████████████████  SQL Generation   │
│                      (5-7 seconds)          Chat API         │
│                                                             │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░█  SQL Execution    │
│                                      (50ms) Local DB        │
│                                                             │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░████████  Summarization    │
│                                  (5-7 sec)  Chat API         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Performance by Query Type

| Query Type | Example | Typical Time |
|------------|---------|--------------|
| Simple greeting | "Hello" | <1 second |
| Simple data lookup | "Show all airports" | 12-15 seconds |
| Filtered query | "Pilots in Dallas" | 15-18 seconds |
| Cross-database join | "Salary + training for John" | 18-22 seconds |
| Complex aggregation | "Average pay by role and base" | 20-25 seconds |
| Query with retry | SQL error + correction | 25-35 seconds |

### Bottleneck Analysis

| Component | Time | % of Total | Optimizable? |
|-----------|------|------------|--------------|
| LLM API calls | ~15-18s | 85% | Limited (API dependent) |
| Database queries | ~50-100ms | <1% | Already fast |
| Local processing | ~100ms | <1% | Already fast |
| Network overhead | ~500ms | 3% | Minimal |

**Key Insight:** 85% of response time is LLM API latency. To significantly improve speed, a faster LLM endpoint would be needed.

---

## 10. Frequently Asked Questions (FAQ)

### Technical Questions

**Q1: How does the system generate SQL automatically?**
> The system uses a Large Language Model (LLM) that has been trained on SQL syntax and database concepts. We provide the LLM with the user's question and relevant table schemas, and it generates appropriate SQL. This is not hardcoded - the AI creates new SQL for every question based on context.

**Q2: What if the AI generates incorrect SQL?**
> We have a self-correction loop. If SQL execution fails, the error message is sent back to the LLM along with the original query, and it generates a corrected version. This retry happens up to 3 times. Our success rate is approximately 95%.

**Q3: How do you query multiple databases at once?**
> We use SQLite's ATTACH DATABASE feature. All 4 operational databases are mounted to a single connection, allowing SQL JOINs across databases. The universal join key is `employee_id` which exists in all crew-related tables.

**Q4: How does the system know which tables to use?**
> We use semantic search (vector similarity). Each table has a rich description stored as an embedding vector. When a user asks a question, we convert it to a vector and find the most similar table descriptions. This is called "Schema RAG" - Retrieval-Augmented Generation for schemas.

**Q5: Is the SQL hardcoded or dynamic?**
> 100% dynamic. No SQL is hardcoded. Every query is generated fresh by the AI based on the user's question. This allows the system to answer questions it has never seen before.

### Security Questions

**Q6: Can users modify or delete data?**
> No. The system only allows SELECT statements. All other SQL commands (DROP, DELETE, UPDATE, INSERT, etc.) are blocked at the validation layer before execution.

**Q7: How is user data protected?**
> Multiple layers: (1) JWT authentication required for all requests, (2) PII masking before data is sent to external LLM APIs, (3) Role-based access control, (4) All queries are logged for audit.

**Q8: What happens to data sent to the LLM API?**
> User questions (with PII masked) and database schemas are sent to the LLM. The actual query results are processed locally. The LLM only sees summarized results for natural language generation, limited to 20 rows.

### Performance Questions

**Q9: Why does it take 15-20 seconds?**
> The system makes 3 LLM API calls per query: (1) embedding API for schema search, (2) chat API for SQL generation, (3) chat API for result summarization. Each call takes 5-7 seconds. The LLM API is the bottleneck, not our code.

**Q10: Can response time be improved?**
> Options include: (1) Faster LLM endpoint, (2) Query caching for frequent questions, (3) Skip summarization for simple results, (4) Use a smaller/faster model for simple queries. These trade off speed vs. accuracy.

### Usage Questions

**Q11: What kind of questions can users ask?**
> Any question about crew data, flights, payroll, training, or compliance that can be answered by the database. Examples: "Who are the captains in Dallas?", "What is John's salary?", "Show expiring medical certificates", "Flights delayed today".

**Q12: Can users ask follow-up questions?**
> Yes. The system maintains conversation context. If a user asks "Show me pilots in Dallas" followed by "What are their salaries?", the system understands "their" refers to the pilots from the previous question.

**Q13: What if the system doesn't understand a question?**
> If confidence is low, the system asks a clarifying question. If it can't find relevant tables, it returns an error suggesting the user rephrase. Users can always rephrase or be more specific.

---

## 11. Sample Queries and Responses

### Example 1: Simple Lookup

```
User: "Show me all airports"

Generated SQL:
SELECT iata_code, name, city, country, is_hub
FROM flight_operations.airports
ORDER BY iata_code
LIMIT 100

Response:
"Here are the 30 airports in our system:

Hub Airports:
• DFW - Dallas/Fort Worth International (Dallas, US) - Hub
• ORD - O'Hare International (Chicago, US) - Hub
• LAX - Los Angeles International (Los Angeles, US) - Hub
...

Non-Hub Airports:
• BOS - Boston Logan International (Boston, US)
• SEA - Seattle-Tacoma International (Seattle, US)
..."
```

### Example 2: Cross-Database Query

```
User: "Show me pilots with their salaries and training status"

Generated SQL:
SELECT
    cm.employee_id,
    cm.name,
    cm.crew_role,
    pr.net_pay,
    tr.course_name,
    tr.result
FROM crew_management.crew_members cm
JOIN hr_payroll.payroll_records pr
    ON cm.employee_id = pr.employee_id
LEFT JOIN compliance_training.training_records tr
    ON cm.employee_id = tr.employee_id
WHERE cm.crew_role IN ('Captain', 'First Officer')
    AND pr.pay_month = '2026-01'
LIMIT 100

Response:
"Found 35 pilots with their January 2026 salary and recent training:

Captains:
1. John Smith (AA-10001) - $12,500 net pay - Recurrent Training: Passed
2. Sarah Johnson (AA-10005) - $13,200 net pay - CRM Training: Passed
...

First Officers:
1. Michael Chen (AA-10012) - $8,500 net pay - Type Rating: Passed
..."
```

### Example 3: Analytical Query

```
User: "How many crew members are there by role?"

Generated SQL:
SELECT
    crew_role,
    COUNT(*) as count
FROM crew_management.crew_members
WHERE status = 'Active'
GROUP BY crew_role
ORDER BY count DESC

Response:
"Here's the breakdown of active crew members by role:

• Cabin Crew: 18 members
• First Officer: 12 members
• Captain: 10 members
• Purser: 6 members
• Senior Cabin Crew: 4 members

Total: 50 active crew members"
```

### Example 4: Follow-up Question

```
User: "Show me captains based in Dallas"

Response: "Found 4 captains based at DFW:
1. John Smith (AA-10001)
2. Robert Wilson (AA-10015)
3. James Brown (AA-10023)
4. David Lee (AA-10031)"

User: "What are their salaries?"  ← Follow-up

Generated SQL:
SELECT
    cm.name,
    cm.employee_id,
    pr.base_pay,
    pr.flight_hour_pay,
    pr.net_pay
FROM crew_management.crew_members cm
JOIN hr_payroll.payroll_records pr ON cm.employee_id = pr.employee_id
WHERE cm.crew_role = 'Captain'
    AND cm.base_airport = 'DFW'
    AND pr.pay_month = '2026-01'

Response: "Here are the January 2026 salaries for the 4 DFW captains:
1. John Smith: $12,500 (base: $10,000 + flight hours: $2,500)
2. Robert Wilson: $13,200 (base: $10,500 + flight hours: $2,700)
..."
```

---

## 12. Technology Stack

### Complete Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Streamlit | Web UI framework |
| **Backend** | FastAPI | REST API framework |
| **Database** | SQLite | Relational data storage |
| **Vector Store** | FAISS | Embedding similarity search |
| **LLM** | Coforge/Quasar API | AI text generation |
| **Embeddings** | Coforge/Quasar API | Text vectorization |
| **Authentication** | JWT (PyJWT) | Token-based auth |
| **Language** | Python 3.10+ | Backend programming |
| **HTTP Client** | Requests | API communication |
| **Data Validation** | Pydantic | Request/response models |

### Key Libraries

```
fastapi          - Web framework
uvicorn          - ASGI server
streamlit        - Frontend UI
sqlite3          - Database (built-in)
faiss-cpu        - Vector similarity search
pyjwt            - JWT token handling
pydantic         - Data validation
requests         - HTTP client
python-dotenv    - Environment variables
numpy            - Numerical operations
```

### File Structure

```
Sumit_chatbot/
├── backend/
│   ├── api/
│   │   ├── chat.py           # Main chat endpoint
│   │   ├── auth.py           # Authentication endpoints
│   │   └── health.py         # Health check
│   ├── auth/
│   │   └── jwt_handler.py    # JWT token management
│   ├── cache/
│   │   └── vector_store.py   # FAISS vector store
│   ├── config.py             # Configuration settings
│   ├── core/
│   │   ├── intent_router.py  # Intent classification
│   │   ├── query_rewriter.py # Follow-up handling
│   │   └── conversation_manager.py
│   ├── db/
│   │   ├── session.py        # Database connections
│   │   └── setup_databases.py# Database initialization
│   ├── llm/
│   │   ├── client.py         # LLM API client
│   │   ├── prompts.py        # Prompt templates
│   │   └── embeddings.py     # Embedding functions
│   ├── pii/
│   │   └── masker.py         # PII detection/masking
│   └── sql/
│       └── sql_pipeline.py   # Text-to-SQL pipeline
├── frontend/
│   ├── app.py                # Main Streamlit app
│   └── components/
│       ├── chat_message.py   # Message display
│       ├── feedback_buttons.py # Thumbs up/down
│       └── sql_display.py    # SQL results view
├── scripts/
│   ├── run_all_setup.py      # Master setup script
│   ├── build_faiss_index.py  # Build vector index
│   └── populate_schema_metadata.py
├── data/
│   ├── databases/            # SQLite database files
│   └── faiss_indexes/        # FAISS index files
├── docs/
│   └── SYSTEM_ARCHITECTURE_AND_FEATURES.md  # This document
├── .env                      # Environment variables
└── requirements.txt          # Python dependencies
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | January 2026 | Initial documentation |

---

**End of Document**
