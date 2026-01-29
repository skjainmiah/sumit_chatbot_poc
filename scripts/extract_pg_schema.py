"""
PostgreSQL Schema Extractor

Extracts database schemas from PostgreSQL and saves them for use in Text-to-SQL prompts.

Features:
- Interactive login (prompts for credentials if not provided)
- Browse and select databases/tables interactively
- Command-line arguments for automation
- Multiple output formats (JSON, text, DDL)

Usage:
    # Interactive mode (prompts for everything)
    python extract_pg_schema.py --interactive

    # With credentials (will prompt for password if not set)
    python extract_pg_schema.py --host localhost --user postgres --interactive

    # Fetch all databases and all tables
    python extract_pg_schema.py --all

    # Fetch specific database(s)
    python extract_pg_schema.py --databases hr_db finance_db

    # Fetch specific tables from specific database
    python extract_pg_schema.py --database hr_db --tables employees departments

    # Custom output file
    python extract_pg_schema.py --all --output my_schema.json
"""

import os
import sys
import json
import argparse
import getpass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Error: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_nullable: bool
    column_default: Optional[str]
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_ref: Optional[str]
    description: Optional[str]


@dataclass
class TableInfo:
    database: str
    schema: str
    name: str
    full_name: str
    description: Optional[str]
    columns: List[ColumnInfo]
    row_count_estimate: int
    primary_keys: List[str]
    foreign_keys: List[Dict[str, str]]
    indexes: List[str]


@dataclass
class DatabaseInfo:
    name: str
    tables: List[TableInfo]
    extracted_at: str


class PostgreSQLSchemaExtractor:
    """Extract schema information from PostgreSQL databases."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        user: str = "postgres",
        password: str = "",
        database: str = "postgres",
        ssl_mode: str = "prefer"
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.default_database = database
        self.ssl_mode = ssl_mode
        self._conn = None

    def _get_connection(self, database: str = None):
        """Get database connection."""
        db = database or self.default_database
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=db,
            sslmode=self.ssl_mode
        )

    def test_connection(self) -> Tuple[bool, str]:
        """Test database connection. Returns (success, message)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            conn.close()
            return True, f"Connected successfully!\nPostgreSQL: {version[:60]}..."
        except Exception as e:
            return False, f"Connection failed: {e}"

    def get_all_databases(self) -> List[str]:
        """Get list of all databases (excluding system databases)."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT datname FROM pg_database
                    WHERE datistemplate = false
                    AND datname NOT IN ('postgres')
                    ORDER BY datname
                """)
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_schemas(self, database: str) -> List[str]:
        """Get list of schemas in a database (excluding system schemas)."""
        conn = self._get_connection(database)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT schema_name FROM information_schema.schemata
                    WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                    AND schema_name NOT LIKE 'pg_%'
                    ORDER BY schema_name
                """)
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_tables(self, database: str, schema: str = "public") -> List[str]:
        """Get list of tables in a schema."""
        conn = self._get_connection(database)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """, (schema,))
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_table_description(self, database: str, schema: str, table: str) -> Optional[str]:
        """Get table comment/description."""
        conn = self._get_connection(database)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT obj_description(
                        (quote_ident(%s) || '.' || quote_ident(%s))::regclass,
                        'pg_class'
                    )
                """, (schema, table))
                result = cur.fetchone()
                return result[0] if result else None
        except:
            return None
        finally:
            conn.close()

    def get_columns(self, database: str, schema: str, table: str) -> List[ColumnInfo]:
        """Get column information for a table."""
        conn = self._get_connection(database)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        c.column_name,
                        c.data_type,
                        c.is_nullable,
                        c.column_default,
                        c.character_maximum_length,
                        c.numeric_precision,
                        c.numeric_scale,
                        pgd.description as column_description
                    FROM information_schema.columns c
                    LEFT JOIN pg_catalog.pg_statio_all_tables st
                        ON c.table_schema = st.schemaname AND c.table_name = st.relname
                    LEFT JOIN pg_catalog.pg_description pgd
                        ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
                    WHERE c.table_schema = %s AND c.table_name = %s
                    ORDER BY c.ordinal_position
                """, (schema, table))
                columns_raw = cur.fetchall()

                # Get primary keys
                cur.execute("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = (quote_ident(%s) || '.' || quote_ident(%s))::regclass
                    AND i.indisprimary
                """, (schema, table))
                primary_keys = {row[0] for row in cur.fetchall()}

                # Get foreign keys
                cur.execute("""
                    SELECT
                        kcu.column_name,
                        ccu.table_schema || '.' || ccu.table_name || '.' || ccu.column_name as references
                    FROM information_schema.key_column_usage kcu
                    JOIN information_schema.constraint_column_usage ccu
                        ON kcu.constraint_name = ccu.constraint_name
                    JOIN information_schema.table_constraints tc
                        ON kcu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.table_schema = %s AND kcu.table_name = %s
                """, (schema, table))
                foreign_keys = {row[0]: row[1] for row in cur.fetchall()}

                columns = []
                for col in columns_raw:
                    data_type = col['data_type']
                    if col['character_maximum_length']:
                        data_type = f"{data_type}({col['character_maximum_length']})"
                    elif col['numeric_precision'] and col['data_type'] == 'numeric':
                        data_type = f"numeric({col['numeric_precision']},{col['numeric_scale'] or 0})"

                    columns.append(ColumnInfo(
                        name=col['column_name'],
                        data_type=data_type,
                        is_nullable=col['is_nullable'] == 'YES',
                        column_default=col['column_default'],
                        is_primary_key=col['column_name'] in primary_keys,
                        is_foreign_key=col['column_name'] in foreign_keys,
                        foreign_key_ref=foreign_keys.get(col['column_name']),
                        description=col['column_description']
                    ))

                return columns
        finally:
            conn.close()

    def get_row_count_estimate(self, database: str, schema: str, table: str) -> int:
        """Get estimated row count (fast, uses statistics)."""
        conn = self._get_connection(database)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT reltuples::bigint
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = %s
                """, (schema, table))
                result = cur.fetchone()
                return max(0, result[0]) if result else 0
        except:
            return 0
        finally:
            conn.close()

    def get_indexes(self, database: str, schema: str, table: str) -> List[str]:
        """Get index names for a table."""
        conn = self._get_connection(database)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                """, (schema, table))
                return [row[0] for row in cur.fetchall()]
        except:
            return []
        finally:
            conn.close()

    def get_foreign_keys(self, database: str, schema: str, table: str) -> List[Dict[str, str]]:
        """Get foreign key relationships."""
        conn = self._get_connection(database)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        kcu.column_name as from_column,
                        ccu.table_schema as to_schema,
                        ccu.table_name as to_table,
                        ccu.column_name as to_column
                    FROM information_schema.key_column_usage kcu
                    JOIN information_schema.constraint_column_usage ccu
                        ON kcu.constraint_name = ccu.constraint_name
                    JOIN information_schema.table_constraints tc
                        ON kcu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.table_schema = %s AND kcu.table_name = %s
                """, (schema, table))
                return [dict(row) for row in cur.fetchall()]
        except:
            return []
        finally:
            conn.close()

    def extract_table(self, database: str, schema: str, table: str) -> TableInfo:
        """Extract complete information for a single table."""
        columns = self.get_columns(database, schema, table)

        return TableInfo(
            database=database,
            schema=schema,
            name=table,
            full_name=f"{schema}.{table}",
            description=self.get_table_description(database, schema, table),
            columns=columns,
            row_count_estimate=self.get_row_count_estimate(database, schema, table),
            primary_keys=[c.name for c in columns if c.is_primary_key],
            foreign_keys=self.get_foreign_keys(database, schema, table),
            indexes=self.get_indexes(database, schema, table)
        )

    def extract_database(
        self,
        database: str,
        schemas: List[str] = None,
        tables: List[str] = None
    ) -> DatabaseInfo:
        """Extract schema information for a database."""
        schemas = schemas or self.get_schemas(database)
        all_tables = []

        for schema in schemas:
            if tables:
                table_list = tables
            else:
                table_list = self.get_tables(database, schema)

            for table in table_list:
                try:
                    table_info = self.extract_table(database, schema, table)
                    all_tables.append(table_info)
                    print(f"  Extracted: {database}.{schema}.{table} ({len(table_info.columns)} columns)")
                except Exception as e:
                    print(f"  Error extracting {database}.{schema}.{table}: {e}")

        return DatabaseInfo(
            name=database,
            tables=all_tables,
            extracted_at=datetime.now().isoformat()
        )

    def extract_all(self, databases: List[str] = None) -> List[DatabaseInfo]:
        """Extract schema information for multiple databases."""
        databases = databases or self.get_all_databases()
        results = []

        for db in databases:
            print(f"\nExtracting database: {db}")
            try:
                db_info = self.extract_database(db)
                results.append(db_info)
            except Exception as e:
                print(f"Error extracting database {db}: {e}")

        return results


def schema_to_dict(schema_data: List[DatabaseInfo]) -> Dict:
    """Convert schema data to dictionary for JSON serialization."""
    return {
        "extracted_at": datetime.now().isoformat(),
        "total_databases": len(schema_data),
        "total_tables": sum(len(db.tables) for db in schema_data),
        "total_columns": sum(
            sum(len(t.columns) for t in db.tables)
            for db in schema_data
        ),
        "databases": [
            {
                "name": db.name,
                "extracted_at": db.extracted_at,
                "table_count": len(db.tables),
                "tables": [
                    {
                        "database": t.database,
                        "schema": t.schema,
                        "name": t.name,
                        "full_name": t.full_name,
                        "description": t.description,
                        "row_count_estimate": t.row_count_estimate,
                        "primary_keys": t.primary_keys,
                        "foreign_keys": t.foreign_keys,
                        "indexes": t.indexes,
                        "column_count": len(t.columns),
                        "columns": [asdict(c) for c in t.columns]
                    }
                    for t in db.tables
                ]
            }
            for db in schema_data
        ]
    }


def schema_to_prompt_format(schema_data: List[DatabaseInfo]) -> str:
    """Convert schema to text format optimized for LLM prompts."""
    lines = []
    lines.append("=" * 80)
    lines.append("DATABASE SCHEMA")
    lines.append("=" * 80)

    total_tables = sum(len(db.tables) for db in schema_data)
    total_columns = sum(sum(len(t.columns) for t in db.tables) for db in schema_data)

    lines.append(f"\nDatabases: {len(schema_data)}")
    lines.append(f"Total Tables: {total_tables}")
    lines.append(f"Total Columns: {total_columns}")
    lines.append("")

    for db in schema_data:
        lines.append(f"\n{'=' * 60}")
        lines.append(f"DATABASE: {db.name}")
        lines.append(f"{'=' * 60}")

        for table in db.tables:
            lines.append(f"\n--- {table.full_name} ---")
            if table.description:
                lines.append(f"Description: {table.description}")
            lines.append(f"Estimated rows: {table.row_count_estimate:,}")

            if table.primary_keys:
                lines.append(f"Primary Key: {', '.join(table.primary_keys)}")

            lines.append("\nColumns:")
            for col in table.columns:
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                pk = " [PK]" if col.is_primary_key else ""
                fk = f" [FK -> {col.foreign_key_ref}]" if col.is_foreign_key else ""
                default = f" DEFAULT {col.column_default}" if col.column_default else ""
                desc = f" -- {col.description}" if col.description else ""

                lines.append(f"  {col.name}: {col.data_type} {nullable}{pk}{fk}{default}{desc}")

            if table.foreign_keys:
                lines.append("\nRelationships:")
                for fk in table.foreign_keys:
                    lines.append(f"  {fk['from_column']} -> {fk['to_schema']}.{fk['to_table']}.{fk['to_column']}")

    return "\n".join(lines)


def schema_to_ddl_format(schema_data: List[DatabaseInfo]) -> str:
    """Convert schema to DDL-like format for prompts."""
    lines = []

    for db in schema_data:
        lines.append(f"-- Database: {db.name}")
        lines.append("")

        for table in db.tables:
            if table.description:
                lines.append(f"-- {table.description}")

            lines.append(f"CREATE TABLE {db.name}.{table.full_name} (")

            col_definitions = []
            for col in table.columns:
                parts = [f"    {col.name}", col.data_type]

                if not col.is_nullable:
                    parts.append("NOT NULL")
                if col.is_primary_key:
                    parts.append("PRIMARY KEY")
                if col.column_default:
                    parts.append(f"DEFAULT {col.column_default}")

                col_def = " ".join(parts)
                if col.description:
                    col_def += f"  -- {col.description}"
                col_definitions.append(col_def)

            for fk in table.foreign_keys:
                fk_def = f"    FOREIGN KEY ({fk['from_column']}) REFERENCES {fk['to_schema']}.{fk['to_table']}({fk['to_column']})"
                col_definitions.append(fk_def)

            lines.append(",\n".join(col_definitions))
            lines.append(");")
            lines.append("")

    return "\n".join(lines)


def interactive_login() -> Dict[str, Any]:
    """Interactive login prompt for PostgreSQL credentials."""
    print("\n" + "=" * 50)
    print("  PostgreSQL Connection Setup")
    print("=" * 50)

    # Get credentials with defaults from environment
    host = input(f"Host [{os.getenv('PGHOST', 'localhost')}]: ").strip()
    host = host or os.getenv('PGHOST', 'localhost')

    port_str = input(f"Port [{os.getenv('PGPORT', '5432')}]: ").strip()
    port = int(port_str) if port_str else int(os.getenv('PGPORT', '5432'))

    user = input(f"Username [{os.getenv('PGUSER', 'postgres')}]: ").strip()
    user = user or os.getenv('PGUSER', 'postgres')

    # Password - use getpass for security
    password = os.getenv('PGPASSWORD', '')
    if password:
        use_env = input("Use password from PGPASSWORD environment variable? [Y/n]: ").strip().lower()
        if use_env == 'n':
            password = getpass.getpass("Password: ")
    else:
        password = getpass.getpass("Password: ")

    database = input(f"Default database [{os.getenv('PGDATABASE', 'postgres')}]: ").strip()
    database = database or os.getenv('PGDATABASE', 'postgres')

    ssl_input = input("SSL mode [prefer/require/disable] (prefer): ").strip().lower()
    ssl_mode = ssl_input if ssl_input in ['prefer', 'require', 'disable'] else 'prefer'

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database,
        'ssl_mode': ssl_mode
    }


def interactive_select_databases(extractor: PostgreSQLSchemaExtractor) -> List[str]:
    """Interactive database selection."""
    print("\n" + "-" * 50)
    print("  Available Databases")
    print("-" * 50)

    databases = extractor.get_all_databases()

    if not databases:
        print("No databases found (excluding system databases)")
        return []

    for i, db in enumerate(databases, 1):
        print(f"  {i}. {db}")

    print(f"\n  A. Select ALL databases")
    print(f"  Q. Quit")

    selection = input("\nEnter numbers separated by comma (e.g., 1,3,5) or 'A' for all: ").strip()

    if selection.upper() == 'Q':
        return []
    if selection.upper() == 'A':
        return databases

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(',')]
        selected = [databases[i] for i in indices if 0 <= i < len(databases)]
        return selected
    except (ValueError, IndexError):
        print("Invalid selection. Selecting all databases.")
        return databases


def interactive_select_tables(extractor: PostgreSQLSchemaExtractor, database: str) -> List[str]:
    """Interactive table selection for a database."""
    print(f"\n" + "-" * 50)
    print(f"  Tables in '{database}'")
    print("-" * 50)

    schemas = extractor.get_schemas(database)
    all_tables = []

    for schema in schemas:
        tables = extractor.get_tables(database, schema)
        for table in tables:
            all_tables.append(f"{schema}.{table}")

    if not all_tables:
        print("No tables found")
        return []

    for i, table in enumerate(all_tables, 1):
        print(f"  {i}. {table}")

    print(f"\n  A. Select ALL tables")
    print(f"  S. Skip this database")

    selection = input("\nEnter numbers separated by comma or 'A' for all: ").strip()

    if selection.upper() == 'S':
        return []
    if selection.upper() == 'A':
        return [t.split('.')[1] for t in all_tables]  # Return just table names

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(',')]
        selected = [all_tables[i].split('.')[1] for i in indices if 0 <= i < len(all_tables)]
        return selected
    except (ValueError, IndexError):
        print("Invalid selection. Selecting all tables.")
        return [t.split('.')[1] for t in all_tables]


def interactive_mode(args):
    """Run in interactive mode with prompts."""
    # Step 1: Login
    if args.host and args.user and (args.password or os.getenv('PGPASSWORD')):
        # Use provided credentials
        credentials = {
            'host': args.host,
            'port': args.port,
            'user': args.user,
            'password': args.password or os.getenv('PGPASSWORD', ''),
            'database': args.dbname,
            'ssl_mode': args.sslmode
        }
    else:
        # Interactive login
        credentials = interactive_login()

    # Step 2: Test connection
    print("\nTesting connection...")
    extractor = PostgreSQLSchemaExtractor(**credentials)
    success, message = extractor.test_connection()

    if not success:
        print(f"\n{message}")
        retry = input("\nRetry with different credentials? [Y/n]: ").strip().lower()
        if retry != 'n':
            return interactive_mode(args)
        return None

    print(f"\n{message}")

    # Step 3: Select databases
    selected_databases = interactive_select_databases(extractor)

    if not selected_databases:
        print("No databases selected. Exiting.")
        return None

    print(f"\nSelected databases: {', '.join(selected_databases)}")

    # Step 4: Select tables (optional)
    select_tables = input("\nSelect specific tables for each database? [y/N]: ").strip().lower()

    database_tables = {}
    if select_tables == 'y':
        for db in selected_databases:
            tables = interactive_select_tables(extractor, db)
            if tables:
                database_tables[db] = tables
    else:
        for db in selected_databases:
            database_tables[db] = None  # None means all tables

    # Step 5: Extract
    print("\n" + "=" * 50)
    print("  Extracting Schema")
    print("=" * 50)

    schema_data = []
    for db, tables in database_tables.items():
        print(f"\nExtracting database: {db}")
        try:
            db_info = extractor.extract_database(db, tables=tables)
            schema_data.append(db_info)
        except Exception as e:
            print(f"Error: {e}")

    return schema_data


def main():
    parser = argparse.ArgumentParser(
        description="Extract PostgreSQL schema for Text-to-SQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for credentials and selections)
  python extract_pg_schema.py --interactive

  # Extract all databases with credentials
  python extract_pg_schema.py --host localhost --user postgres --all

  # Extract specific database
  python extract_pg_schema.py --database mydb

  # Extract specific tables from a database
  python extract_pg_schema.py --database mydb --tables users orders products

  # Use environment variables for connection
  export PGHOST=localhost PGPORT=5432 PGUSER=postgres PGPASSWORD=secret
  python extract_pg_schema.py --all
        """
    )

    # Connection arguments
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"),
                        help="PostgreSQL host (default: localhost or PGHOST env)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")),
                        help="PostgreSQL port (default: 5432 or PGPORT env)")
    parser.add_argument("--user", "-U", default=os.getenv("PGUSER", "postgres"),
                        help="PostgreSQL user (default: postgres or PGUSER env)")
    parser.add_argument("--password", "-W", default=None,
                        help="PostgreSQL password (default: PGPASSWORD env, or prompts)")
    parser.add_argument("--dbname", "-d", default=os.getenv("PGDATABASE", "postgres"),
                        help="Default database to connect (default: postgres or PGDATABASE env)")
    parser.add_argument("--sslmode", default="prefer",
                        choices=["disable", "prefer", "require"],
                        help="SSL mode (default: prefer)")

    # Mode selection
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode - prompts for credentials and database/table selection")

    # Extraction scope
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--all", "-a", action="store_true",
                       help="Extract all databases and tables")
    scope.add_argument("--databases", nargs="+", metavar="DB",
                       help="Extract specific database(s)")
    scope.add_argument("--database", metavar="DB",
                       help="Extract from a single database")

    # Table selection (only with --database)
    parser.add_argument("--tables", "-t", nargs="+", metavar="TABLE",
                        help="Specific tables to extract (requires --database)")
    parser.add_argument("--all-tables", action="store_true",
                        help="Extract all tables from database (default)")
    parser.add_argument("--schemas", "-s", nargs="+", default=["public"], metavar="SCHEMA",
                        help="Schemas to extract from (default: public)")

    # Output options
    parser.add_argument("--output", "-o", default="data/schema/full_schema.json",
                        help="Output file path (default: data/schema/full_schema.json)")
    parser.add_argument("--format", "-f", choices=["json", "text", "ddl", "all"], default="all",
                        help="Output format (default: all)")

    args = parser.parse_args()

    # Validate arguments
    if args.tables and not args.database:
        parser.error("--tables requires --database")

    # Check if we need to prompt for password
    if not args.password and not os.getenv("PGPASSWORD") and not args.interactive:
        args.password = getpass.getpass("PostgreSQL password: ")

    print("=" * 60)
    print("  PostgreSQL Schema Extractor")
    print("=" * 60)

    # Interactive mode
    if args.interactive:
        schema_data = interactive_mode(args)
        if not schema_data:
            sys.exit(1)
    else:
        # Non-interactive mode
        password = args.password or os.getenv("PGPASSWORD", "")

        extractor = PostgreSQLSchemaExtractor(
            host=args.host,
            port=args.port,
            user=args.user,
            password=password,
            database=args.dbname,
            ssl_mode=args.sslmode
        )

        # Test connection
        print(f"\nConnecting to PostgreSQL at {args.host}:{args.port}...")
        success, message = extractor.test_connection()
        if not success:
            print(message)
            sys.exit(1)
        print(message)

        # Extract schema
        print("\nExtracting schema...")

        if args.all:
            schema_data = extractor.extract_all()
        elif args.databases:
            schema_data = extractor.extract_all(databases=args.databases)
        elif args.database:
            db_info = extractor.extract_database(
                database=args.database,
                schemas=args.schemas,
                tables=args.tables
            )
            schema_data = [db_info]
        else:
            # Default: interactive database selection or all
            print("\nNo database specified. Use --all, --database, or --interactive")
            print("Defaulting to --all")
            schema_data = extractor.extract_all()

    if not schema_data:
        print("No schema data extracted!")
        sys.exit(1)

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save in requested format(s)
    base_path = output_path.with_suffix("")

    if args.format in ["json", "all"]:
        json_path = base_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(schema_to_dict(schema_data), f, indent=2)
        print(f"\nSaved JSON schema to: {json_path}")

    if args.format in ["text", "all"]:
        text_path = base_path.with_suffix(".txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(schema_to_prompt_format(schema_data))
        print(f"Saved text schema to: {text_path}")

    if args.format in ["ddl", "all"]:
        ddl_path = base_path.with_name(base_path.name + "_ddl").with_suffix(".sql")
        with open(ddl_path, "w", encoding="utf-8") as f:
            f.write(schema_to_ddl_format(schema_data))
        print(f"Saved DDL schema to: {ddl_path}")

    # Summary
    total_tables = sum(len(db.tables) for db in schema_data)
    total_columns = sum(sum(len(t.columns) for t in db.tables) for db in schema_data)

    print(f"\n{'=' * 40}")
    print("EXTRACTION COMPLETE")
    print(f"{'=' * 40}")
    print(f"Databases: {len(schema_data)}")
    print(f"Tables: {total_tables}")
    print(f"Columns: {total_columns}")
    print(f"Estimated prompt tokens: ~{total_columns * 15:,}")
    print(f"\nSchema saved to: {output_path.parent}/")


if __name__ == "__main__":
    main()
