"""PostgreSQL to SQLite converter.

Converts PostgreSQL data types and syntax to SQLite equivalents.
"""
import re
from typing import Dict, List, Optional, Tuple
from backend.sql_upload.pg_parser import ParsedTable, ParsedInsert


# PostgreSQL to SQLite type mapping
PG_TO_SQLITE_TYPES = {
    # Serial types -> INTEGER PRIMARY KEY AUTOINCREMENT
    "SERIAL": "INTEGER",
    "BIGSERIAL": "INTEGER",
    "SMALLSERIAL": "INTEGER",

    # Integer types
    "INTEGER": "INTEGER",
    "INT": "INTEGER",
    "INT4": "INTEGER",
    "INT8": "INTEGER",
    "BIGINT": "INTEGER",
    "SMALLINT": "INTEGER",
    "INT2": "INTEGER",

    # Text types
    "VARCHAR": "TEXT",
    "CHARACTER VARYING": "TEXT",
    "CHAR": "TEXT",
    "CHARACTER": "TEXT",
    "TEXT": "TEXT",
    "BPCHAR": "TEXT",
    "NAME": "TEXT",
    "CITEXT": "TEXT",

    # Boolean
    "BOOLEAN": "INTEGER",
    "BOOL": "INTEGER",

    # Numeric/Decimal
    "NUMERIC": "REAL",
    "DECIMAL": "REAL",
    "REAL": "REAL",
    "FLOAT": "REAL",
    "FLOAT4": "REAL",
    "FLOAT8": "REAL",
    "DOUBLE PRECISION": "REAL",
    "DOUBLE": "REAL",
    "MONEY": "REAL",

    # Date/Time -> TEXT (ISO format)
    "TIMESTAMP": "TEXT",
    "TIMESTAMP WITH TIME ZONE": "TEXT",
    "TIMESTAMP WITHOUT TIME ZONE": "TEXT",
    "TIMESTAMPTZ": "TEXT",
    "DATE": "TEXT",
    "TIME": "TEXT",
    "TIME WITH TIME ZONE": "TEXT",
    "TIME WITHOUT TIME ZONE": "TEXT",
    "TIMETZ": "TEXT",
    "INTERVAL": "TEXT",

    # JSON types -> TEXT
    "JSON": "TEXT",
    "JSONB": "TEXT",

    # UUID -> TEXT
    "UUID": "TEXT",

    # Binary
    "BYTEA": "BLOB",

    # Arrays -> TEXT (JSON serialized)
    "ARRAY": "TEXT",

    # Other types -> TEXT
    "INET": "TEXT",
    "CIDR": "TEXT",
    "MACADDR": "TEXT",
    "MACADDR8": "TEXT",
    "BIT": "TEXT",
    "BIT VARYING": "TEXT",
    "VARBIT": "TEXT",
    "TSVECTOR": "TEXT",
    "TSQUERY": "TEXT",
    "XML": "TEXT",
    "POINT": "TEXT",
    "LINE": "TEXT",
    "LSEG": "TEXT",
    "BOX": "TEXT",
    "PATH": "TEXT",
    "POLYGON": "TEXT",
    "CIRCLE": "TEXT",
    "OID": "INTEGER",
}


class PgToSqliteConverter:
    """Convert PostgreSQL SQL to SQLite compatible SQL."""

    def __init__(self):
        self.type_mapping = PG_TO_SQLITE_TYPES.copy()

    def convert_type(self, pg_type: str) -> str:
        """Convert a PostgreSQL type to SQLite type."""
        # Normalize type name
        pg_type_upper = pg_type.upper().strip()

        # Remove array brackets
        pg_type_upper = re.sub(r'\[\]$', '', pg_type_upper)

        # Remove precision/scale for numeric types
        base_type = re.sub(r'\(\d+(?:,\s*\d+)?\)', '', pg_type_upper).strip()

        # Direct mapping
        if base_type in self.type_mapping:
            return self.type_mapping[base_type]

        # Check for partial matches
        for pg_t, sqlite_t in self.type_mapping.items():
            if base_type.startswith(pg_t):
                return sqlite_t

        # Default to TEXT for unknown types
        return "TEXT"

    def is_serial_type(self, pg_type: str) -> bool:
        """Check if type is a serial (auto-increment) type."""
        pg_type_upper = pg_type.upper().strip()
        return pg_type_upper in ("SERIAL", "BIGSERIAL", "SMALLSERIAL")

    def convert_table(self, table: ParsedTable) -> str:
        """Convert a ParsedTable to SQLite CREATE TABLE statement."""
        columns_sql = []
        pk_columns = []

        for col in table.columns:
            col_name = col["name"]
            pg_type = col["type"]
            sqlite_type = self.convert_type(pg_type)

            # Build column definition
            col_def = f'"{col_name}" {sqlite_type}'

            # Handle SERIAL types - make them PRIMARY KEY AUTOINCREMENT
            if self.is_serial_type(pg_type):
                col_def = f'"{col_name}" INTEGER PRIMARY KEY AUTOINCREMENT'
                pk_columns.append(col_name)
            else:
                # Handle explicit PRIMARY KEY
                if col.get("is_primary_key"):
                    pk_columns.append(col_name)

                # Handle NOT NULL
                if col.get("is_not_null") and not col.get("is_primary_key"):
                    col_def += " NOT NULL"

                # Handle DEFAULT - convert PostgreSQL defaults to SQLite
                if col.get("default"):
                    default_val = self._convert_default(col["default"], sqlite_type)
                    if default_val:
                        col_def += f" DEFAULT {default_val}"

            columns_sql.append(col_def)

        # Add PRIMARY KEY constraint if multiple columns and not already added
        if len(pk_columns) > 1:
            pk_names = ", ".join(f'"{c}"' for c in pk_columns)
            columns_sql.append(f"PRIMARY KEY ({pk_names})")
        elif len(pk_columns) == 1 and not any(self.is_serial_type(c.get("type", "")) for c in table.columns):
            # Single column PK that's not a serial
            for i, col_sql in enumerate(columns_sql):
                if pk_columns[0] in col_sql and "PRIMARY KEY" not in col_sql:
                    columns_sql[i] += " PRIMARY KEY"
                    break

        # Build final statement
        columns_str = ",\n    ".join(columns_sql)
        return f'CREATE TABLE IF NOT EXISTS "{table.name}" (\n    {columns_str}\n);'

    def _convert_default(self, pg_default: str, sqlite_type: str) -> Optional[str]:
        """Convert PostgreSQL DEFAULT value to SQLite."""
        if not pg_default:
            return None

        pg_default_upper = pg_default.upper()

        # Skip sequence-related defaults (handled by AUTOINCREMENT)
        if "NEXTVAL" in pg_default_upper:
            return None

        # Handle common PostgreSQL functions
        if pg_default_upper in ("NOW()", "CURRENT_TIMESTAMP"):
            return "CURRENT_TIMESTAMP"
        if pg_default_upper == "CURRENT_DATE":
            return "CURRENT_DATE"
        if pg_default_upper == "CURRENT_TIME":
            return "CURRENT_TIME"

        # Handle boolean values
        if pg_default_upper == "TRUE":
            return "1"
        if pg_default_upper == "FALSE":
            return "0"

        # Handle NULL
        if pg_default_upper == "NULL":
            return "NULL"

        # Handle type casting (e.g., '0'::integer)
        cast_match = re.match(r"'([^']*)'::[\w\s]+", pg_default)
        if cast_match:
            value = cast_match.group(1)
            if sqlite_type == "INTEGER":
                try:
                    return str(int(value))
                except ValueError:
                    return f"'{value}'"
            elif sqlite_type == "REAL":
                try:
                    return str(float(value))
                except ValueError:
                    return f"'{value}'"
            return f"'{value}'"

        # Handle numeric type casting without quotes
        cast_match2 = re.match(r"(\d+(?:\.\d+)?)::", pg_default)
        if cast_match2:
            return cast_match2.group(1)

        # Return as-is if it looks safe
        if re.match(r"^[\d.]+$", pg_default):
            return pg_default
        if re.match(r"^'[^']*'$", pg_default):
            return pg_default

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
                    # Escape single quotes
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
        """Convert a PostgreSQL value to SQLite compatible value."""
        if value is None or value.upper() == "NULL":
            return "NULL"

        # Boolean conversion
        if value.upper() in ("TRUE", "T", "YES", "Y", "ON", "1"):
            return "1"
        if value.upper() in ("FALSE", "F", "NO", "N", "OFF", "0"):
            return "0"

        # Handle PostgreSQL array syntax
        if value.startswith("{") and value.endswith("}"):
            # Convert to JSON array format
            items = value[1:-1].split(",")
            json_items = [f'"{item.strip()}"' for item in items if item.strip()]
            return f"'[{', '.join(json_items)}]'"

        # Escape quotes for text
        if target_type == "TEXT":
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        return value
