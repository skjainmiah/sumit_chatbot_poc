"""Schema loader - loads extracted schema for use in prompts."""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass


@dataclass
class SchemaStats:
    total_databases: int
    total_tables: int
    total_columns: int
    estimated_tokens: int


def _get_visible_db_names() -> Set[str]:
    """Get set of visible database names from registry."""
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        return set(registry.get_visible_databases().keys())
    except Exception:
        return set()


class SchemaLoader:
    """Load and manage database schema for prompts."""

    _instance = None
    _schema_data = None
    _schema_text = None
    _visible_schema_text = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, schema_path: str = None):
        if self._schema_data is None:
            self._schema_path = schema_path or self._find_schema_file()
            self._load_schema()

    def _find_schema_file(self) -> Optional[str]:
        """Find schema file in standard locations. Returns None if not found."""
        base_dir = Path(__file__).parent.parent.parent
        possible_paths = [
            base_dir / "data" / "schema" / "full_schema.json",
            base_dir / "data" / "schema.json",
            base_dir / "schema.json",
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        return None

    def _load_schema(self):
        """Load schema from JSON file and merge uploaded database schemas."""
        if self._schema_path:
            print(f"Loading schema from: {self._schema_path}")
            with open(self._schema_path, "r", encoding="utf-8") as f:
                self._schema_data = json.load(f)
        else:
            print("No schema JSON file found, loading from registry only")
            self._schema_data = {
                "databases": [],
                "total_databases": 0,
                "total_tables": 0,
                "total_columns": 0,
            }

        # Merge uploaded database schemas from schema_metadata
        self._merge_uploaded_schemas()

        # Pre-generate text format for prompts
        self._schema_text = self._generate_prompt_schema()

        stats = self.get_stats()
        print(f"Schema loaded: {stats.total_databases} databases, "
              f"{stats.total_tables} tables, {stats.total_columns} columns "
              f"(~{stats.estimated_tokens:,} tokens)")

    def _merge_uploaded_schemas(self):
        """Load database schemas from schema_metadata and merge any missing ones into schema data.

        This ensures all databases (mock + uploaded) appear in the schema even
        if the JSON file is missing or doesn't contain them.
        """
        try:
            from backend.config import settings
            from backend.db.registry import get_database_registry

            registry = get_database_registry()
            all_dbs = registry.get_all_databases()

            # Find databases in registry that are NOT already in schema_data
            existing_db_names = {db["name"] for db in self._schema_data["databases"]}
            missing_dbs = {
                name: info for name, info in all_dbs.items()
                if name not in existing_db_names and name != "app"
            }

            if not missing_dbs:
                return

            # Load schema_metadata for missing databases
            conn = sqlite3.connect(settings.app_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            placeholders = ",".join("?" * len(missing_dbs))
            cursor.execute(f"""
                SELECT db_name, table_name, column_details, row_count,
                       sample_values, ddl_statement, llm_description,
                       detected_foreign_keys
                FROM schema_metadata
                WHERE db_name IN ({placeholders})
            """, tuple(missing_dbs.keys()))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return

            # Group by database
            db_tables: Dict[str, List] = {}
            for row in rows:
                db_name = row["db_name"]
                if db_name not in db_tables:
                    db_tables[db_name] = []

                # Parse detected FK data
                fk_list = []
                fk_columns = set()
                fk_ref_map = {}  # column_name -> "to_table.to_column"
                if row["detected_foreign_keys"]:
                    try:
                        fk_list = json.loads(row["detected_foreign_keys"])
                        for fk in fk_list:
                            fk_columns.add(fk["from_column"])
                            fk_ref_map[fk["from_column"]] = f"{fk['to_table']}.{fk['to_column']}"
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Parse columns from column_details (format: "col1 (TYPE), col2 (TYPE)")
                columns = []
                if row["column_details"]:
                    for col_str in row["column_details"].split(", "):
                        parts = col_str.split(" (")
                        if len(parts) >= 2:
                            col_name = parts[0].strip()
                            col_type = parts[1].rstrip(")")
                            columns.append({
                                "name": col_name,
                                "data_type": col_type,
                                "is_primary_key": False,
                                "is_nullable": True,
                                "is_foreign_key": col_name in fk_columns,
                                "foreign_key_ref": fk_ref_map.get(col_name, ""),
                            })

                # Build foreign_keys list for table-level relationships
                table_fks = []
                for fk in fk_list:
                    table_fks.append({
                        "from_column": fk["from_column"],
                        "to_schema": db_name,
                        "to_table": fk["to_table"],
                        "to_column": fk["to_column"],
                    })

                db_tables[db_name].append({
                    "name": row["table_name"],
                    "full_name": row["table_name"],
                    "description": row["llm_description"] or "",
                    "row_count_estimate": row["row_count"] or 0,
                    "primary_keys": [],
                    "columns": columns,
                    "foreign_keys": table_fks,
                })

            # Add to schema_data
            added_tables = 0
            added_columns = 0
            for db_name, tables in db_tables.items():
                self._schema_data["databases"].append({
                    "name": db_name,
                    "tables": tables,
                })
                added_tables += len(tables)
                added_columns += sum(len(t["columns"]) for t in tables)

            # Update totals
            self._schema_data["total_databases"] = len(self._schema_data["databases"])
            self._schema_data["total_tables"] = self._schema_data.get("total_tables", 0) + added_tables
            self._schema_data["total_columns"] = self._schema_data.get("total_columns", 0) + added_columns

            print(f"Merged {len(db_tables)} uploaded database(s) into schema "
                  f"({added_tables} tables, {added_columns} columns)")

        except Exception as e:
            print(f"Warning: Could not merge uploaded schemas: {e}")

    def _generate_prompt_schema(self, all_dbs: Set[str] = None) -> str:
        """Generate optimized schema text for LLM prompts.

        Args:
            all_dbs: Set of visible database names to include. If None, include all.
        """
        lines = []

        # Filter databases if visibility set provided
        databases = self._schema_data["databases"]
        if all_dbs:
            databases = [db for db in databases if db["name"] in all_dbs]

        if not databases:
            return "No databases available."

        # Summary header
        lines.append("=" * 70)
        lines.append("AVAILABLE DATABASES AND TABLES")
        lines.append("=" * 70)

        db_names = [db["name"] for db in databases]
        total_tables = sum(len(db["tables"]) for db in databases)
        lines.append(f"\nDatabases: {', '.join(db_names)}")
        lines.append(f"Total Tables: {total_tables}")
        lines.append("")

        for db in databases:
            lines.append(f"\n{'─' * 60}")
            lines.append(f"DATABASE: {db['name']}")
            lines.append(f"{'─' * 60}")

            for table in db["tables"]:
                # Use db_name.table_name format (SQLite compatible)
                table_name = table.get("name", table.get("full_name", ""))
                qualified_name = f"{db['name']}.{table_name}"

                # Table header
                lines.append(f"\n■ {qualified_name}")
                if table.get("description"):
                    lines.append(f"  Description: {table['description']}")
                if table.get("row_count_estimate", 0) > 0:
                    lines.append(f"  Rows: ~{table['row_count_estimate']:,}")

                # Primary keys
                if table.get("primary_keys"):
                    lines.append(f"  Primary Key: {', '.join(table['primary_keys'])}")

                # Columns
                lines.append("  Columns:")
                for col in table["columns"]:
                    col_line = f"    • {col['name']}: {col['data_type']}"

                    flags = []
                    if col.get("is_primary_key"):
                        flags.append("PK")
                    if col.get("is_foreign_key"):
                        flags.append(f"FK→{col.get('foreign_key_ref', '?')}")
                    if not col.get("is_nullable", True):
                        flags.append("NOT NULL")

                    if flags:
                        col_line += f" [{', '.join(flags)}]"

                    if col.get("description"):
                        col_line += f" -- {col['description']}"

                    lines.append(col_line)

                # Foreign key relationships
                if table.get("foreign_keys"):
                    lines.append("  Relationships:")
                    for fk in table["foreign_keys"]:
                        lines.append(
                            f"    → {fk['from_column']} references "
                            f"{fk.get('to_table', '?')}.{fk.get('to_column', '?')}"
                        )

        return "\n".join(lines)

    def get_schema_text(self, visible_only: bool = True) -> str:
        """Get schema text for prompts.

        Args:
            visible_only: If True, only include visible databases from registry.
        """
        if not visible_only:
            return self._schema_text

        # Generate filtered schema text based on visibility
        all_dbs = _get_visible_db_names()
        if not all_dbs:
            # No registry or all visible
            return self._schema_text

        return self._generate_prompt_schema(all_dbs)

    def get_schema_data(self) -> Dict:
        """Get raw schema data."""
        return self._schema_data

    def get_stats(self) -> SchemaStats:
        """Get schema statistics."""
        return SchemaStats(
            total_databases=self._schema_data.get("total_databases", 0),
            total_tables=self._schema_data.get("total_tables", 0),
            total_columns=self._schema_data.get("total_columns", 0),
            estimated_tokens=self._schema_data.get("total_columns", 0) * 15
        )

    def get_database_names(self, visible_only: bool = True) -> List[str]:
        """Get list of database names.

        Args:
            visible_only: If True, only return visible databases from registry.
        """
        all_names = [db["name"] for db in self._schema_data["databases"]]

        if not visible_only:
            return all_names

        all_dbs = _get_visible_db_names()
        if not all_dbs:
            return all_names

        return [name for name in all_names if name in all_dbs]

    def get_table_names(self, database: str = None, visible_only: bool = True) -> List[str]:
        """Get list of table names, optionally filtered by database.

        Args:
            database: Filter to specific database name.
            visible_only: If True, only include tables from visible databases.
        """
        all_dbs = _get_visible_db_names() if visible_only else set()

        tables = []
        for db in self._schema_data["databases"]:
            if database and db["name"] != database:
                continue
            if visible_only and all_dbs and db["name"] not in all_dbs:
                continue
            for table in db["tables"]:
                table_name = table.get("name", table.get("full_name", ""))
                tables.append(f"{db['name']}.{table_name}")
        return tables

    def get_table_info(self, database: str, table: str) -> Optional[Dict]:
        """Get info for a specific table."""
        for db in self._schema_data["databases"]:
            if db["name"] == database:
                for t in db["tables"]:
                    if t["name"] == table or t["full_name"] == table:
                        return t
        return None

    def get_relationships(self) -> List[Dict]:
        """Get all foreign key relationships."""
        relationships = []
        for db in self._schema_data["databases"]:
            for table in db["tables"]:
                for fk in table.get("foreign_keys", []):
                    relationships.append({
                        "from_db": db["name"],
                        "from_table": table["full_name"],
                        "from_column": fk["from_column"],
                        "to_table": f"{fk['to_schema']}.{fk['to_table']}",
                        "to_column": fk["to_column"]
                    })
        return relationships

    def get_meta_info(self) -> str:
        """Get meta information for answering questions about the database structure."""
        lines = [
            "DATABASE STRUCTURE INFORMATION:",
            f"",
            f"Available Databases ({self._schema_data['total_databases']}):",
        ]

        for db in self._schema_data["databases"]:
            lines.append(f"  • {db['name']} ({len(db['tables'])} tables)")
            for table in db["tables"]:
                col_count = len(table["columns"])
                lines.append(f"      - {table['full_name']} ({col_count} columns)")

        lines.append(f"\nTotal: {self._schema_data['total_tables']} tables, "
                     f"{self._schema_data['total_columns']} columns")

        return "\n".join(lines)

    def reload(self):
        """Reload schema from file and uploaded databases."""
        self._schema_data = None
        self._schema_text = None
        self._schema_path = self._find_schema_file()
        self._load_schema()


# Singleton accessor
_schema_loader: Optional[SchemaLoader] = None


def get_schema_loader(schema_path: str = None) -> SchemaLoader:
    """Get schema loader singleton."""
    global _schema_loader
    if _schema_loader is None:
        _schema_loader = SchemaLoader(schema_path)
    return _schema_loader


def reload_schema():
    """Force reload schema from file."""
    global _schema_loader
    if _schema_loader:
        _schema_loader.reload()
