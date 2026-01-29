"""Database creator - creates SQLite databases from parsed SQL."""
import sqlite3
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass

from backend.config import settings
from backend.sql_upload.pg_parser import ParsedDatabase as PgParsedDatabase
from backend.sql_upload.mssql_parser import ParsedDatabase as MssqlParsedDatabase
from backend.sql_upload.pg_to_sqlite import PgToSqliteConverter
from backend.sql_upload.mssql_to_sqlite import MssqlToSqliteConverter

# Type alias for parsed databases from either parser
ParsedDatabase = Union[PgParsedDatabase, MssqlParsedDatabase]


@dataclass
class CreationResult:
    """Result of database creation."""
    success: bool
    db_name: str
    db_path: str
    tables_created: int
    rows_inserted: int
    errors: List[str]


class DatabaseCreator:
    """Creates SQLite databases from parsed PostgreSQL or MSSQL dumps."""

    def __init__(self, output_dir: str = None, dialect: str = "postgresql"):
        self.output_dir = output_dir or settings.DATABASE_DIR
        self.dialect = dialect

        # Select appropriate converter
        if dialect == "mssql":
            self.converter = MssqlToSqliteConverter()
        else:
            self.converter = PgToSqliteConverter()

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def set_dialect(self, dialect: str):
        """Change the SQL dialect and converter."""
        self.dialect = dialect
        if dialect == "mssql":
            self.converter = MssqlToSqliteConverter()
        else:
            self.converter = PgToSqliteConverter()

    def sanitize_db_name(self, name: str) -> str:
        """Sanitize database name for use as filename."""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[^\w\-]', '_', name.lower())
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        # Ensure not empty
        if not sanitized:
            sanitized = "imported_db"
        return sanitized

    def get_unique_db_path(self, base_name: str) -> Tuple[str, str]:
        """Get a unique database path, appending number if name exists."""
        sanitized = self.sanitize_db_name(base_name)
        db_name = sanitized
        db_path = os.path.join(self.output_dir, f"{sanitized}.db")

        counter = 1
        while os.path.exists(db_path):
            db_name = f"{sanitized}_{counter}"
            db_path = os.path.join(self.output_dir, f"{db_name}.db")
            counter += 1

        return db_name, db_path

    def create_database(self, parsed_db: ParsedDatabase) -> CreationResult:
        """Create a SQLite database from parsed SQL dump (PostgreSQL or MSSQL)."""
        db_name, db_path = self.get_unique_db_path(parsed_db.name)
        errors = []
        tables_created = 0
        rows_inserted = 0

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON;")

            # Create tables
            for table in parsed_db.tables:
                try:
                    create_sql = self.converter.convert_table(table)
                    cursor.execute(create_sql)
                    tables_created += 1
                except sqlite3.Error as e:
                    errors.append(f"Error creating table {table.name}: {str(e)}")

            # Insert data
            for insert in parsed_db.inserts:
                try:
                    insert_statements = self.converter.convert_insert(insert)
                    for stmt in insert_statements:
                        try:
                            cursor.execute(stmt)
                            rows_inserted += 1
                        except sqlite3.Error as e:
                            # Log but don't fail on individual insert errors
                            if len(errors) < 10:  # Limit error accumulation
                                errors.append(f"Insert error in {insert.table_name}: {str(e)[:100]}")
                except Exception as e:
                    if len(errors) < 10:
                        errors.append(f"Error processing inserts for {insert.table_name}: {str(e)[:100]}")

            conn.commit()
            conn.close()

            return CreationResult(
                success=True,
                db_name=db_name,
                db_path=db_path,
                tables_created=tables_created,
                rows_inserted=rows_inserted,
                errors=errors
            )

        except Exception as e:
            # Clean up failed database
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except OSError:
                    pass

            return CreationResult(
                success=False,
                db_name=db_name,
                db_path=db_path,
                tables_created=0,
                rows_inserted=0,
                errors=[f"Database creation failed: {str(e)}"]
            )

    def create_databases(self, parsed_databases: List[ParsedDatabase]) -> List[CreationResult]:
        """Create multiple SQLite databases from parsed dumps."""
        results = []
        for parsed_db in parsed_databases:
            result = self.create_database(parsed_db)
            results.append(result)
        return results

    def get_table_count(self, db_path: str) -> int:
        """Get number of tables in a database."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except sqlite3.Error:
            return 0

    def get_row_counts(self, db_path: str) -> Dict[str, int]:
        """Get row counts for all tables in a database."""
        counts = {}
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    counts[table] = cursor.fetchone()[0]
                except sqlite3.Error:
                    counts[table] = 0

            conn.close()
        except sqlite3.Error:
            pass
        return counts

    def validate_database(self, db_path: str) -> Tuple[bool, List[str]]:
        """Validate a created database."""
        errors = []

        if not os.path.exists(db_path):
            return False, ["Database file does not exist"]

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check integrity
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            if integrity != "ok":
                errors.append(f"Integrity check failed: {integrity}")

            # Check for tables
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            table_count = cursor.fetchone()[0]
            if table_count == 0:
                errors.append("No tables found in database")

            conn.close()

            return len(errors) == 0, errors

        except sqlite3.Error as e:
            return False, [f"Database validation error: {str(e)}"]
