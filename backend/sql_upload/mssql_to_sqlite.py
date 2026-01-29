"""Microsoft SQL Server to SQLite converter.

Converts MSSQL data types and syntax to SQLite equivalents.
"""
import re
from typing import Dict, List, Optional
from backend.sql_upload.mssql_parser import ParsedTable, ParsedInsert


# MSSQL to SQLite type mapping
MSSQL_TO_SQLITE_TYPES = {
    # Integer types
    "INT": "INTEGER",
    "INTEGER": "INTEGER",
    "BIGINT": "INTEGER",
    "SMALLINT": "INTEGER",
    "TINYINT": "INTEGER",

    # String types
    "VARCHAR": "TEXT",
    "NVARCHAR": "TEXT",
    "CHAR": "TEXT",
    "NCHAR": "TEXT",
    "TEXT": "TEXT",
    "NTEXT": "TEXT",
    "SYSNAME": "TEXT",

    # Binary types
    "BINARY": "BLOB",
    "VARBINARY": "BLOB",
    "IMAGE": "BLOB",

    # Boolean (BIT)
    "BIT": "INTEGER",

    # Numeric/Decimal
    "DECIMAL": "REAL",
    "NUMERIC": "REAL",
    "MONEY": "REAL",
    "SMALLMONEY": "REAL",
    "FLOAT": "REAL",
    "REAL": "REAL",

    # Date/Time -> TEXT (ISO format)
    "DATE": "TEXT",
    "TIME": "TEXT",
    "DATETIME": "TEXT",
    "DATETIME2": "TEXT",
    "SMALLDATETIME": "TEXT",
    "DATETIMEOFFSET": "TEXT",
    "TIMESTAMP": "BLOB",  # MSSQL timestamp is actually rowversion

    # GUID
    "UNIQUEIDENTIFIER": "TEXT",

    # XML
    "XML": "TEXT",

    # SQL Variant
    "SQL_VARIANT": "TEXT",

    # Geography/Geometry
    "GEOGRAPHY": "TEXT",
    "GEOMETRY": "TEXT",

    # Hierarchyid
    "HIERARCHYID": "TEXT",
}


class MssqlToSqliteConverter:
    """Convert MSSQL SQL to SQLite compatible SQL."""

    def __init__(self):
        self.type_mapping = MSSQL_TO_SQLITE_TYPES.copy()

    def convert_type(self, mssql_type: str) -> str:
        """Convert an MSSQL type to SQLite type."""
        # Normalize type name - remove size specifications and brackets
        mssql_type_clean = mssql_type.upper().strip()
        mssql_type_clean = re.sub(r'\[|\]', '', mssql_type_clean)

        # Extract base type (before parentheses)
        base_type = re.sub(r'\(.*\)', '', mssql_type_clean).strip()

        # Handle MAX keyword
        base_type = base_type.replace('(MAX)', '')

        # Direct mapping
        if base_type in self.type_mapping:
            return self.type_mapping[base_type]

        # Check for partial matches
        for mssql_t, sqlite_t in self.type_mapping.items():
            if base_type.startswith(mssql_t):
                return sqlite_t

        # Default to TEXT for unknown types
        return "TEXT"

    def is_identity_column(self, column: Dict) -> bool:
        """Check if column is an IDENTITY column (auto-increment)."""
        return column.get("is_identity", False) or "IDENTITY" in column.get("raw", "").upper()

    def convert_table(self, table: ParsedTable) -> str:
        """Convert a ParsedTable to SQLite CREATE TABLE statement."""
        columns_sql = []
        pk_columns = []

        for col in table.columns:
            col_name = col["name"]
            mssql_type = col["type"]
            sqlite_type = self.convert_type(mssql_type)

            # Build column definition
            if self.is_identity_column(col):
                # IDENTITY columns become INTEGER PRIMARY KEY AUTOINCREMENT
                col_def = f'"{col_name}" INTEGER PRIMARY KEY AUTOINCREMENT'
                pk_columns.append(col_name)
            else:
                col_def = f'"{col_name}" {sqlite_type}'

                # Handle explicit PRIMARY KEY
                if col.get("is_primary_key"):
                    pk_columns.append(col_name)

                # Handle NOT NULL
                if col.get("is_not_null") and not col.get("is_primary_key"):
                    col_def += " NOT NULL"

                # Handle DEFAULT
                if col.get("default"):
                    default_val = self._convert_default(col["default"], sqlite_type)
                    if default_val:
                        col_def += f" DEFAULT {default_val}"

            columns_sql.append(col_def)

        # Add PRIMARY KEY constraint if multiple columns and not already added via IDENTITY
        identity_cols = [c for c in table.columns if self.is_identity_column(c)]
        if len(pk_columns) > 1 and not identity_cols:
            pk_names = ", ".join(f'"{c}"' for c in pk_columns)
            columns_sql.append(f"PRIMARY KEY ({pk_names})")
        elif len(pk_columns) == 1 and not identity_cols:
            # Single column PK that's not an IDENTITY
            for i, col_sql in enumerate(columns_sql):
                if pk_columns[0] in col_sql and "PRIMARY KEY" not in col_sql:
                    columns_sql[i] += " PRIMARY KEY"
                    break

        # Build final statement
        columns_str = ",\n    ".join(columns_sql)
        return f'CREATE TABLE IF NOT EXISTS "{table.name}" (\n    {columns_str}\n);'

    def _convert_default(self, mssql_default: str, sqlite_type: str) -> Optional[str]:
        """Convert MSSQL DEFAULT value to SQLite."""
        if not mssql_default:
            return None

        # Remove outer parentheses if present
        default = mssql_default.strip()
        while default.startswith("(") and default.endswith(")"):
            default = default[1:-1].strip()

        default_upper = default.upper()

        # Handle common MSSQL functions
        if default_upper in ("GETDATE()", "CURRENT_TIMESTAMP", "SYSDATETIME()"):
            return "CURRENT_TIMESTAMP"
        if default_upper == "GETUTCDATE()":
            return "CURRENT_TIMESTAMP"
        if default_upper in ("NEWID()", "NEWSEQUENTIALID()"):
            return None  # No equivalent in SQLite
        if default_upper == "SUSER_SNAME()":
            return None
        if default_upper == "HOST_NAME()":
            return None

        # Handle NULL
        if default_upper == "NULL":
            return "NULL"

        # Handle boolean/bit values
        if default_upper in ("1", "0", "(1)", "(0)"):
            return default.strip("()")

        # Handle string literals
        if default.startswith("N'") and default.endswith("'"):
            return default[1:]  # Remove N prefix
        if default.startswith("'") and default.endswith("'"):
            return default

        # Handle numeric values
        if re.match(r'^-?\d+(\.\d+)?$', default):
            return default

        # Skip complex expressions
        return None

    def convert_insert(self, insert: ParsedInsert) -> List[str]:
        """Convert a ParsedInsert to SQLite INSERT statements."""
        if not insert.values:
            return []

        statements = []
        table_name = insert.table_name

        if insert.columns:
            columns_str = ", ".join(f'"{c}"' for c in insert.columns)
            base_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES '
        else:
            base_sql = f'INSERT INTO "{table_name}" VALUES '

        for row in insert.values:
            values_list = []
            for val in row:
                if val is None:
                    values_list.append("NULL")
                elif isinstance(val, str):
                    # Handle MSSQL unicode prefix and escape quotes
                    if val.startswith("N'") and val.endswith("'"):
                        val = val[2:-1]
                    escaped = val.replace("'", "''")
                    values_list.append(f"'{escaped}'")
                elif isinstance(val, bool):
                    values_list.append("1" if val else "0")
                else:
                    values_list.append(str(val))

            values_str = ", ".join(values_list)
            statements.append(f"{base_sql}({values_str});")

        return statements

    def convert_value(self, value: str, target_type: str = "TEXT") -> str:
        """Convert an MSSQL value to SQLite compatible value."""
        if value is None or value.upper() == "NULL":
            return "NULL"

        # Handle bit/boolean values
        if value in ("1", "0", "True", "False"):
            return "1" if value in ("1", "True") else "0"

        # Handle unicode string prefix
        if value.startswith("N'") and value.endswith("'"):
            value = value[2:-1]
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        # Handle regular strings
        if target_type == "TEXT":
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        return value
