Done! The script now has interactive login and database/table selection. Here's how to use it:

  Usage Options                                                                                                                       
  1. Interactive Mode (Recommended for first time)                                                                                 
  
  python scripts/extract_pg_schema.py --interactive

  This will prompt you for:
  - Host, Port, Username, Password
  - Select databases from a list
  - Optionally select specific tables

  2. With Credentials (prompts for password)

  python scripts/extract_pg_schema.py --host myserver --user myuser --interactive

  3. Full Command Line (for automation)

  python scripts/extract_pg_schema.py --host localhost --user postgres --password secret --database mydb --all-tables

  4. Using Environment Variables

  set PGHOST=localhost
  set PGPORT=5432
  set PGUSER=postgres
  set PGPASSWORD=secret

  python scripts/extract_pg_schema.py --all

  ---
  Interactive Flow

  ============================================================
    PostgreSQL Schema Extractor
  ============================================================

  ==================================================
    PostgreSQL Connection Setup
  ==================================================
  Host [localhost]: myserver.com
  Port [5432]:
  Username [postgres]: admin
  Password: ********
  Default database [postgres]:
  SSL mode [prefer/require/disable] (prefer):

  Testing connection...
  Connected successfully!
  PostgreSQL: PostgreSQL 14.5 on x86_64-pc-linux-gnu...

  --------------------------------------------------
    Available Databases
  --------------------------------------------------
    1. hr_db
    2. sales_db
    3. finance_db

    A. Select ALL databases
    Q. Quit

  Enter numbers separated by comma (e.g., 1,3,5) or 'A' for all: 1,2

  Selected databases: hr_db, sales_db

  Select specific tables for each database? [y/N]: y

  --------------------------------------------------
    Tables in 'hr_db'
  --------------------------------------------------
    1. public.employees
    2. public.departments
    3. public.salaries

    A. Select ALL tables
    S. Skip this database

  Enter numbers separated by comma or 'A' for all: 1,2

  ---
  Output Location

  All schema files are saved to: data/schema/

  data/schema/
  ├── full_schema.json    ← Used by chatbot
  ├── full_schema.txt     ← Human readable
  └── full_schema_ddl.sql ← DDL format