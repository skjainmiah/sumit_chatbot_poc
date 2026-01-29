# V2 Migration Guide: SQLite → PostgreSQL

## What Changed

| Component | V1 (Old) | V2 (New) |
|-----------|----------|----------|
| Database | SQLite (4 .db files) | PostgreSQL |
| Schema retrieval | FAISS vector search | Full schema in prompt |
| LLM calls | 3+ per query | 1-2 per query |
| Meta questions | Hardcoded responses | Dynamic from schema |
| Expected latency | 8+ seconds | 2-4 seconds |

## New Files Created

```
scripts/
├── extract_pg_schema.py     # PostgreSQL schema extractor

backend/
├── db/
│   └── postgres.py          # PostgreSQL connection manager
├── schema/
│   ├── __init__.py
│   └── loader.py            # Schema loader for prompts
├── sql/
│   └── pipeline_v2.py       # New SQL pipeline (no FAISS)
├── api/
│   └── chat_v2.py           # New chat API endpoints
└── main.py                  # Updated to include v2 routes

data/
└── schema/
    └── sample_schema.json   # Sample schema for testing

docs/
├── scaling_recommendations.md
├── setup_postgresql.md
└── v2_migration_guide.md    # This file

env.postgres.example         # PostgreSQL environment template
```

## Quick Start

### 1. Install dependencies
```bash
pip install psycopg2-binary
```

### 2. Configure PostgreSQL
```bash
# Copy and edit environment file
cp env.postgres.example .env

# Set your PostgreSQL credentials
PGHOST=your_host
PGPORT=5432
PGUSER=your_user
PGPASSWORD=your_password
PGDATABASE=postgres
```

### 3. Extract schema
```bash
# Extract all databases
python scripts/extract_pg_schema.py --all

# Or extract specific database
python scripts/extract_pg_schema.py --database your_db --all-tables
```

### 4. Test the pipeline
```bash
python scripts/test_pipeline_v2.py
```

### 5. Start the server
```bash
# Enable PostgreSQL mode
export USE_POSTGRES=true

# Start server
uvicorn backend.main:app --reload --port 8000
```

### 6. Test the API
```bash
# Health check
curl http://localhost:8000/api/v2/chat/health

# Send a message
curl -X POST http://localhost:8000/api/v2/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "List available databases"}'

# Get schema info
curl http://localhost:8000/api/v2/chat/schema/info
```

## API Endpoints

### V2 Chat API (`/api/v2/chat/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/message` | POST | Send chat message |
| `/schema/info` | GET | Get schema statistics |
| `/schema/tables` | GET | List tables (optional: ?database=name) |
| `/schema/reload` | POST | Reload schema from file |
| `/health` | GET | Health check |

### Message Request
```json
{
  "message": "Show all employees",
  "conversation_id": "optional_id",
  "context": "optional previous context"
}
```

### Message Response
```json
{
  "success": true,
  "response": "Natural language response",
  "intent": "meta|data|ambiguous|general|error",
  "conversation_id": "conv_123",
  "sql_query": "SELECT ... (if data intent)",
  "sql_results": { "columns": [], "rows": [], "row_count": 0 },
  "clarification": "Clarifying question (if ambiguous)",
  "processing_time_ms": 1234,
  "error": null
}
```

## How It Works

### Query Flow
```
User Question
      ↓
[Is it a greeting?] → Yes → Return greeting
      ↓ No
[Is it a meta question?] → Yes → Return schema info (no LLM)
      ↓ No
[Send to LLM with full schema]
      ↓
LLM Response: {intent, sql/answer/clarification}
      ↓
[If data intent] → Execute SQL → Summarize results
      ↓
Return Response
```

### Why Full Schema Works

For 25 tables with ~50 columns each:
- Total columns: ~1,250
- Estimated tokens: ~15,000-20,000
- LLM context window: 128,000+
- Plenty of room for schema + question + few-shot examples

### Benefits
1. **Accuracy**: LLM sees ALL tables, picks the right ones
2. **Speed**: No FAISS embedding step, fewer LLM calls
3. **Meta questions**: Answered directly from loaded schema
4. **Relationships**: Foreign keys visible, better JOINs

## Troubleshooting

### "Schema file not found"
Run the schema extractor:
```bash
python scripts/extract_pg_schema.py --all
```

### "Connection refused"
Check PostgreSQL is running and credentials are correct in `.env`

### "Permission denied"
Your PostgreSQL user needs SELECT on `information_schema`:
```sql
GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO your_user;
```

### Slow responses
- Check LLM API latency
- Consider using a faster model for simple queries
- Enable query caching (future feature)

## Reverting to V1

If you need to switch back to SQLite:
```bash
# Disable PostgreSQL mode
export USE_POSTGRES=false

# V1 endpoints still available at /api/chat/
```

Both v1 and v2 APIs can run simultaneously.
