# V2 Setup Commands - PostgreSQL Schema Extraction

## Quick Reference

| Item | Location |
|------|----------|
| **Schema JSON** | `data/schema/full_schema.json` |
| **Schema Text** | `data/schema/full_schema.txt` |
| **Schema DDL** | `data/schema/full_schema_ddl.sql` |
| **Extractor Script** | `scripts/extract_pg_schema.py` |
| **Setup Script (Win)** | `scripts/setup_v2.bat` |
| **Setup Script (Unix)** | `scripts/setup_v2.sh` |

---

## Step-by-Step Commands

### Step 1: Navigate to Project Directory

```bash
cd C:\Users\skjai\Project\Sumit_chatbot
```

### Step 2: Install PostgreSQL Driver

```bash
pip install psycopg2-binary
```

### Step 3: Set PostgreSQL Credentials

**Windows (Command Prompt):**
```cmd
set PGHOST=your_database_host
set PGPORT=5432
set PGUSER=your_username
set PGPASSWORD=your_password
set PGDATABASE=your_default_database
```

**Windows (PowerShell):**
```powershell
$env:PGHOST = "your_database_host"
$env:PGPORT = "5432"
$env:PGUSER = "your_username"
$env:PGPASSWORD = "your_password"
$env:PGDATABASE = "your_default_database"
```

**Linux/Mac:**
```bash
export PGHOST=your_database_host
export PGPORT=5432
export PGUSER=your_username
export PGPASSWORD=your_password
export PGDATABASE=your_default_database
```

**Or add to .env file:**
```
PGHOST=your_database_host
PGPORT=5432
PGUSER=your_username
PGPASSWORD=your_password
PGDATABASE=your_default_database
```

### Step 4: Create Schema Directory

```bash
mkdir data\schema
# or on Linux/Mac:
mkdir -p data/schema
```

### Step 5: Extract Schema

**Option A - Extract ALL databases:**
```bash
python scripts/extract_pg_schema.py --all
```

**Option B - Extract specific database:**
```bash
python scripts/extract_pg_schema.py --database mydb --all-tables
```

**Option C - Extract specific tables:**
```bash
python scripts/extract_pg_schema.py --database mydb --tables users orders products
```

**Option D - Extract multiple databases:**
```bash
python scripts/extract_pg_schema.py --databases hr_db sales_db finance_db
```

### Step 6: Verify Extraction

```bash
python -c "from backend.schema.loader import get_schema_loader; l = get_schema_loader(); print(f'Tables: {l.get_stats().total_tables}')"
```

### Step 7: Start the Application

**Terminal 1 - Backend:**
```bash
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
streamlit run frontend/app.py
```

### Step 8: Test V2 API

```bash
curl http://localhost:8000/api/v2/chat/health
```

---

## Schema File Location

The chatbot looks for schema in this order:

1. `data/schema/full_schema.json` **(default)**
2. `data/schema.json`
3. `schema.json`

**Always use the default location:** `data/schema/full_schema.json`

---

## Common Extraction Commands

### Extract with Custom Output Path
```bash
python scripts/extract_pg_schema.py --all --output data/schema/full_schema.json
```

### Extract Only Public Schema
```bash
python scripts/extract_pg_schema.py --database mydb --schemas public
```

### Extract Multiple Schemas
```bash
python scripts/extract_pg_schema.py --database mydb --schemas public analytics staging
```

### Output Only JSON (no text/DDL files)
```bash
python scripts/extract_pg_schema.py --all --format json
```

### Output All Formats
```bash
python scripts/extract_pg_schema.py --all --format all
```

---

## Re-extracting After Schema Changes

When your database schema changes (new tables, columns, etc.):

```bash
# Re-run extraction
python scripts/extract_pg_schema.py --all

# Reload in running application (via API)
curl -X POST http://localhost:8000/api/v2/chat/schema/reload
```

---

## Automated Setup

### Windows
```cmd
scripts\setup_v2.bat
```

### Linux/Mac
```bash
chmod +x scripts/setup_v2.sh
./scripts/setup_v2.sh
```

---

## Troubleshooting

### "Connection refused"
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check credentials
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "SELECT 1"
```

### "Schema file not found"
```bash
# Verify file exists
ls data/schema/full_schema.json

# If not, run extraction
python scripts/extract_pg_schema.py --all
```

### "Permission denied"
```sql
-- Grant permissions to your user
GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO your_user;
GRANT SELECT ON ALL TABLES IN SCHEMA pg_catalog TO your_user;
```

### Check extraction output
```bash
# View schema summary
python -c "
from backend.schema.loader import get_schema_loader
l = get_schema_loader()
print('Databases:', l.get_database_names())
print('Total tables:', l.get_stats().total_tables)
print('Total columns:', l.get_stats().total_columns)
"
```

---

## File Structure After Setup

```
Sumit_chatbot/
├── data/
│   └── schema/
│       ├── full_schema.json      ← Main schema file (used by chatbot)
│       ├── full_schema.txt       ← Human-readable version
│       └── full_schema_ddl.sql   ← DDL format
├── scripts/
│   ├── extract_pg_schema.py      ← Schema extractor
│   ├── setup_v2.bat              ← Windows setup script
│   ├── setup_v2.sh               ← Linux/Mac setup script
│   └── README_SETUP.md           ← This file
└── ...
```

---

## Summary Commands (Copy-Paste Ready)

```bash
# Complete setup sequence
cd C:\Users\skjai\Project\Sumit_chatbot
pip install psycopg2-binary
set PGHOST=localhost
set PGPORT=5432
set PGUSER=postgres
set PGPASSWORD=your_password
set PGDATABASE=postgres
mkdir data\schema
python scripts/extract_pg_schema.py --all
uvicorn backend.main:app --reload --port 8000
```
