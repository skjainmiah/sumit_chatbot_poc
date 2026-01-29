@echo off
REM ============================================================
REM V2 Setup Script for Windows
REM PostgreSQL Schema Extraction and Chatbot Setup
REM ============================================================

echo.
echo ============================================================
echo   CHATBOT V2 SETUP - PostgreSQL with Full Schema
echo ============================================================
echo.

REM Check if we're in the right directory
if not exist "backend" (
    echo ERROR: Please run this script from the project root directory
    echo        cd C:\Users\skjai\Project\Sumit_chatbot
    exit /b 1
)

REM Step 1: Install dependencies
echo.
echo [Step 1/5] Installing Python dependencies...
echo ------------------------------------------------------------
pip install psycopg2-binary
if %errorlevel% neq 0 (
    echo ERROR: Failed to install psycopg2-binary
    exit /b 1
)
echo Done.

REM Step 2: Check environment variables
echo.
echo [Step 2/5] Checking PostgreSQL configuration...
echo ------------------------------------------------------------

if "%PGHOST%"=="" (
    echo WARNING: PGHOST not set. Using default: localhost
    set PGHOST=localhost
)
if "%PGPORT%"=="" (
    echo WARNING: PGPORT not set. Using default: 5432
    set PGPORT=5432
)
if "%PGUSER%"=="" (
    echo ERROR: PGUSER not set!
    echo Please set PostgreSQL credentials:
    echo   set PGHOST=your_host
    echo   set PGPORT=5432
    echo   set PGUSER=your_username
    echo   set PGPASSWORD=your_password
    echo   set PGDATABASE=your_database
    exit /b 1
)
if "%PGPASSWORD%"=="" (
    echo ERROR: PGPASSWORD not set!
    exit /b 1
)

echo PostgreSQL Config:
echo   Host: %PGHOST%
echo   Port: %PGPORT%
echo   User: %PGUSER%
echo   Database: %PGDATABASE%
echo Done.

REM Step 3: Create schema directory
echo.
echo [Step 3/5] Creating schema directory...
echo ------------------------------------------------------------
if not exist "data\schema" mkdir data\schema
echo Directory: data\schema\
echo Done.

REM Step 4: Extract schema
echo.
echo [Step 4/5] Extracting PostgreSQL schema...
echo ------------------------------------------------------------
echo Running: python scripts/extract_pg_schema.py --all
echo.

python scripts/extract_pg_schema.py --all --output data/schema/full_schema.json

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Schema extraction failed!
    echo Check your PostgreSQL connection settings.
    exit /b 1
)

echo.
echo Schema files created:
echo   - data\schema\full_schema.json  (used by chatbot)
echo   - data\schema\full_schema.txt   (human readable)
echo   - data\schema\full_schema_ddl.sql (DDL format)
echo Done.

REM Step 5: Verify
echo.
echo [Step 5/5] Verifying setup...
echo ------------------------------------------------------------
python -c "from backend.schema.loader import get_schema_loader; l = get_schema_loader(); print(f'Loaded: {l.get_stats().total_tables} tables from {l.get_stats().total_databases} databases')"

if %errorlevel% neq 0 (
    echo ERROR: Schema verification failed!
    exit /b 1
)

echo.
echo ============================================================
echo   SETUP COMPLETE!
echo ============================================================
echo.
echo Schema stored at: data\schema\full_schema.json
echo.
echo Next steps:
echo   1. Start backend:  uvicorn backend.main:app --reload --port 8000
echo   2. Start frontend: streamlit run frontend/app.py
echo   3. Select "Chat V2 (PostgreSQL)" in the sidebar
echo.
echo To re-extract schema after database changes:
echo   python scripts/extract_pg_schema.py --all
echo.
