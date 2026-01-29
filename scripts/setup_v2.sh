#!/bin/bash
# ============================================================
# V2 Setup Script for Linux/Mac
# PostgreSQL Schema Extraction and Chatbot Setup
# ============================================================

set -e  # Exit on error

echo ""
echo "============================================================"
echo "  CHATBOT V2 SETUP - PostgreSQL with Full Schema"
echo "============================================================"
echo ""

# Check if we're in the right directory
if [ ! -d "backend" ]; then
    echo "ERROR: Please run this script from the project root directory"
    echo "       cd /path/to/Sumit_chatbot"
    exit 1
fi

# Step 1: Install dependencies
echo ""
echo "[Step 1/5] Installing Python dependencies..."
echo "------------------------------------------------------------"
pip install psycopg2-binary
echo "Done."

# Step 2: Check environment variables
echo ""
echo "[Step 2/5] Checking PostgreSQL configuration..."
echo "------------------------------------------------------------"

if [ -z "$PGHOST" ]; then
    echo "WARNING: PGHOST not set. Using default: localhost"
    export PGHOST=localhost
fi
if [ -z "$PGPORT" ]; then
    echo "WARNING: PGPORT not set. Using default: 5432"
    export PGPORT=5432
fi
if [ -z "$PGUSER" ]; then
    echo "ERROR: PGUSER not set!"
    echo "Please set PostgreSQL credentials:"
    echo "  export PGHOST=your_host"
    echo "  export PGPORT=5432"
    echo "  export PGUSER=your_username"
    echo "  export PGPASSWORD=your_password"
    echo "  export PGDATABASE=your_database"
    exit 1
fi
if [ -z "$PGPASSWORD" ]; then
    echo "ERROR: PGPASSWORD not set!"
    exit 1
fi

echo "PostgreSQL Config:"
echo "  Host: $PGHOST"
echo "  Port: $PGPORT"
echo "  User: $PGUSER"
echo "  Database: $PGDATABASE"
echo "Done."

# Step 3: Create schema directory
echo ""
echo "[Step 3/5] Creating schema directory..."
echo "------------------------------------------------------------"
mkdir -p data/schema
echo "Directory: data/schema/"
echo "Done."

# Step 4: Extract schema
echo ""
echo "[Step 4/5] Extracting PostgreSQL schema..."
echo "------------------------------------------------------------"
echo "Running: python scripts/extract_pg_schema.py --all"
echo ""

python scripts/extract_pg_schema.py --all --output data/schema/full_schema.json

echo ""
echo "Schema files created:"
echo "  - data/schema/full_schema.json  (used by chatbot)"
echo "  - data/schema/full_schema.txt   (human readable)"
echo "  - data/schema/full_schema_ddl.sql (DDL format)"
echo "Done."

# Step 5: Verify
echo ""
echo "[Step 5/5] Verifying setup..."
echo "------------------------------------------------------------"
python -c "from backend.schema.loader import get_schema_loader; l = get_schema_loader(); print(f'Loaded: {l.get_stats().total_tables} tables from {l.get_stats().total_databases} databases')"

echo ""
echo "============================================================"
echo "  SETUP COMPLETE!"
echo "============================================================"
echo ""
echo "Schema stored at: data/schema/full_schema.json"
echo ""
echo "Next steps:"
echo "  1. Start backend:  uvicorn backend.main:app --reload --port 8000"
echo "  2. Start frontend: streamlit run frontend/app.py"
echo "  3. Select 'Chat V2 (PostgreSQL)' in the sidebar"
echo ""
echo "To re-extract schema after database changes:"
echo "  python scripts/extract_pg_schema.py --all"
echo ""
