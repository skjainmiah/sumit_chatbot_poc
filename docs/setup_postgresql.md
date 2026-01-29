# PostgreSQL Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and fill in your PostgreSQL credentials:

```bash
cp env.postgres.example .env
```

Edit `.env` with your PostgreSQL connection details:
```
PGHOST=your_host
PGPORT=5432
PGUSER=your_user
PGPASSWORD=your_password
PGDATABASE=postgres
```

### 3. Extract Schema

Run the schema extractor to pull your database structure:

```bash
# Extract all databases
python scripts/extract_pg_schema.py --all

# Extract specific database
python scripts/extract_pg_schema.py --database my_database

# Extract specific tables
python scripts/extract_pg_schema.py --database my_database --tables users orders products

# Custom output location
python scripts/extract_pg_schema.py --all --output data/schema/my_schema.json
```

### 4. Verify Extraction

Check the generated files in `data/schema/`:
- `full_schema.json` - Machine-readable schema (used by chatbot)
- `full_schema.txt` - Human-readable schema
- `full_schema_ddl.sql` - DDL format

### 5. Run the Application

```bash
# Start backend
uvicorn backend.main:app --reload --port 8000

# Start frontend (in another terminal)
streamlit run frontend/app.py
```

---

## Schema Extractor Options

### Connection Options

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| `--host` | `PGHOST` | localhost | PostgreSQL host |
| `--port` | `PGPORT` | 5432 | PostgreSQL port |
| `--user` | `PGUSER` | postgres | Database user |
| `--password` | `PGPASSWORD` | (empty) | Database password |
| `--dbname` | `PGDATABASE` | postgres | Default database |
| `--sslmode` | - | prefer | SSL mode |

### Extraction Scope

| Option | Description |
|--------|-------------|
| `--all` | Extract all databases and tables |
| `--databases DB1 DB2` | Extract specific databases |
| `--database DB` | Extract from single database |
| `--tables T1 T2` | Extract specific tables (requires `--database`) |
| `--schemas S1 S2` | Schemas to extract (default: public) |

### Output Options

| Option | Default | Description |
|--------|---------|-------------|
| `--output` | `data/schema/full_schema.json` | Output file path |
| `--format` | `all` | Output format: json, text, ddl, or all |

---

## Examples

### Extract HR and Finance databases only
```bash
python scripts/extract_pg_schema.py --databases hr_db finance_db
```

### Extract specific tables from a database
```bash
python scripts/extract_pg_schema.py --database hr_db --tables employees departments salaries
```

### Extract from non-public schema
```bash
python scripts/extract_pg_schema.py --database my_db --schemas public analytics
```

### Use environment variables
```bash
export PGHOST=prod-db.company.com
export PGPORT=5432
export PGUSER=readonly_user
export PGPASSWORD=secret
python scripts/extract_pg_schema.py --all
```

---

## Token Estimation

After extraction, the script shows estimated token count:

```
Databases: 4
Tables: 25
Columns: 1,250
Estimated prompt tokens: ~18,750
```

**Guidelines:**
- < 30K tokens: Full schema approach works well
- 30K-80K tokens: Still works, monitor response quality
- > 80K tokens: Consider hierarchical approach

---

## Troubleshooting

### Connection refused
```
Error: could not connect to server: Connection refused
```
- Check PostgreSQL is running
- Verify host and port
- Check firewall rules

### Authentication failed
```
Error: password authentication failed for user "postgres"
```
- Verify username and password
- Check pg_hba.conf for allowed connections

### Permission denied
```
Error: permission denied for table users
```
- User needs SELECT permission on information_schema
- Grant: `GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO your_user;`

### SSL required
```
Error: SSL connection is required
```
- Set `--sslmode require` or `PGSSLMODE=require`

---

## Updating Schema

When your database schema changes, re-run the extractor:

```bash
python scripts/extract_pg_schema.py --all
```

The chatbot will automatically use the updated schema on next startup.

For live updates without restart:
```python
from backend.schema import reload_schema
reload_schema()
```
