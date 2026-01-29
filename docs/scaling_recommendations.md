# Text-to-SQL Scaling Recommendations

## Token Estimation by Scale

| Tables | Columns/Table | Total Columns | Est. Tokens | Approach |
|--------|---------------|---------------|-------------|----------|
| 25     | 50            | 1,250         | ~15K-20K    | Full schema in prompt |
| 50     | 50            | 2,500         | ~30K-40K    | Full schema in prompt |
| 100    | 50            | 5,000         | ~60K-80K    | Full schema (borderline) |
| 500    | 50            | 25,000        | ~300K+      | Hierarchical / Catalog |
| 1000+  | 50            | 50,000+       | ~600K+      | Semantic layer required |

## Recommended Approaches by Scale

### Small Scale (25-50 Tables)
- **Approach:** Full schema in every prompt
- **Retrieval:** None needed
- **Pros:** Most accurate, simple architecture
- **Cons:** Higher token cost per query
- **Latency:** Fast (single LLM call)

### Medium Scale (50-100 Tables)
- **Approach:** Full schema in prompt, consider compression
- **Retrieval:** Optional LLM-based table selection
- **Optimizations:**
  - Remove verbose column descriptions
  - Use abbreviated type names
  - Group related tables

### Large Scale (100-500 Tables)
- **Approach:** Two-stage retrieval
- **Stage 1:** LLM selects relevant tables from lightweight catalog
- **Stage 2:** Full schema of selected tables only
- **Retrieval:** Hybrid (BM25 + Vector + Schema Graph)

### Enterprise Scale (1000+ Tables)
- **Approach:** Semantic layer + hierarchical routing
- **Components:**
  - Domain classification (HR, Finance, Ops, etc.)
  - Database selection within domain
  - Table selection within database
  - Fine-tuned SQL model (SQLCoder, NSQL)
- **Retrieval:** Knowledge graph + usage analytics + hybrid search
- **Infrastructure:** Data catalog (Alation, Atlan, Collibra)

## Production Best Practices

### 1. Metadata Enrichment
- Add business descriptions to tables/columns
- Define relationships (FKs, logical joins)
- Track column statistics (cardinality, null %, sample values)

### 2. Query Caching
- Cache generated SQL for identical questions
- Cache query results with TTL
- Learn from successful query patterns

### 3. Few-Shot Examples
- Include 3-5 example queries per domain
- Show complex JOIN patterns
- Demonstrate date/time handling

### 4. Error Handling
- Self-correction loop (max 2-3 retries)
- Fallback to clarifying questions
- Log failed queries for analysis

### 5. Security
- Row-level security based on user role
- Column masking for sensitive data (SSN, salary)
- Audit logging for compliance

## Current Implementation (25 Tables)

For this project with 25 tables and ~50 columns each:

```
Estimated tokens: ~15,000-20,000 tokens
Context window: 128,000+ tokens
Approach: Full schema in prompt
LLM calls: 1-2 per query (generate + summarize)
Expected latency: 2-4 seconds
```

### Architecture
```
User Question
      ↓
[Full Schema + Few-shot Examples + Question]
      ↓
    LLM
      ↓
SQL Query or Clarifying Question or Direct Answer
      ↓
Execute on PostgreSQL
      ↓
Format Results
```
