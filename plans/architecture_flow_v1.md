# Architecture Flow Diagrams (Mermaid)

Generated from codepaths in:
- [`frontend/app.py`](frontend/app.py:1)
- [`frontend/api_client.py`](frontend/api_client.py:1)
- [`frontend/views/chat.py`](frontend/views/chat.py:1)
- [`frontend/views/chat_v2.py`](frontend/views/chat_v2.py:1)
- [`backend/main.py`](backend/main.py:1)
- [`backend/api/router.py`](backend/api/router.py:1)
- [`backend/api/chat.py`](backend/api/chat.py:1)
- [`backend/api/chat_v2.py`](backend/api/chat_v2.py:1)
- [`backend/sql/sql_pipeline.py`](backend/sql/sql_pipeline.py:1)
- [`backend/sql/pipeline_v2.py`](backend/sql/pipeline_v2.py:1)
- [`backend/db/session.py`](backend/db/session.py:1)
- [`backend/cache/vector_store.py`](backend/cache/vector_store.py:1)

## Diagram 1: High-level component architecture

```mermaid
flowchart TB
  U[User] -->|Uses| FE[Streamlit Frontend]
  FE -->|HTTP JSON| API[FastAPI Backend]

  subgraph Frontend
    FE --> VLogin[Login View]
    FE --> VChat1[Chat V1 View]
    FE --> VChat2[Chat V2 View]
    FE --> VDB[Database Explorer]
    FE --> VAdmin[Admin Panel]

    VLogin --> AC[API Client]
    VChat1 --> AC
    VChat2 --> AC
    VDB --> AC
    VAdmin --> AC
  end

  subgraph Backend
    API --> RAuth[/api/auth/*/]
    API --> RChat1[/api/chat/*/]
    API --> RChat2[/api/v2/chat/*/]
    API --> RDB[/api/database/*/]
    API --> RAdmin[/api/admin/*/]
    API --> RHealth[/api/health/]

    RChat1 --> CM[Conversation Manager
app.db persistence]
    RChat1 --> PII[PII Masker]
    RChat1 --> RW[Query Rewriter]
    RChat1 --> IR[Intent Router]
    RChat1 --> SP1[SQL Pipeline V1]
    RChat1 --> GC[General Chat Prompt]

    RChat2 --> PII
    RChat2 --> SP2[SQL Pipeline V2]

    SP1 --> SR1[Schema Retrieval
Keyword + FAISS]
    SR1 --> VS[Vector Store
FAISS indexes]
    SP1 --> LLM1[LLM Client]
    SP1 --> DBX[SQLite Multi-DB Executor
ATTACH databases]
    SP1 --> SUM1[LLM Summarizer]

    SP2 --> SL[Schema Loader
Full schema text]
    SP2 --> LLM2[LLM Client]
    SP2 --> DBX
    SP2 --> SUM2[LLM Summarizer]
    SP2 --> CORR[LLM SQL Correction
on SQL error]

    RDB --> REG[DB Registry
visibility]
    RDB --> UP[Upload Service
SQL or CSV]
    UP --> REG
    UP --> SL
  end

  subgraph DataStores
    SQLITE[(SQLite operational DBs)]
    APPDB[(app.db)]
    FAISS[(FAISS index files)]
    SCHEMA[(Schema JSON)]
  end

  CM --> APPDB
  DBX --> SQLITE
  VS --> FAISS
  SL --> SCHEMA

  LLM1 --> LLMAPI[External LLM Router API]
  LLM2 --> LLMAPI
  IR --> LLMAPI
  RW --> LLMAPI
```

## Diagram 2: Chat V1 request flow (sequence)

```mermaid
sequenceDiagram
  participant User
  participant FE as Streamlit
  participant AC as API Client
  participant API as FastAPI
  participant Auth as JWT Verify
  participant CM as Conversation Manager
  participant PII as PII Masker
  participant RW as Query Rewriter
  participant IR as Intent Router
  participant SP1 as SQL Pipeline V1
  participant SR1 as Schema Retrieval
  participant VS as FAISS Vector Store
  participant LLM as LLM Router API
