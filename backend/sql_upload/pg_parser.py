"""PostgreSQL dump file parser.

Parses pg_dump and pg_dumpall output files to extract:
- Database names (from pg_dumpall)
- CREATE TABLE statements
- INSERT statements
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedTable:
    """Represents a parsed CREATE TABLE statement."""
    name: str
    schema: str = "public"
    columns: List[Dict] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    raw_sql: str = ""


@dataclass
class ParsedInsert:
    """Represents a parsed INSERT statement."""
    table_name: str
    columns: List[str] = field(default_factory=list)
    values: List[Tuple] = field(default_factory=list)
    raw_sql: str = ""


@dataclass
class ParsedDatabase:
    """Represents a parsed database from pg_dumpall."""
    name: str
    tables: List[ParsedTable] = field(default_factory=list)
    inserts: List[ParsedInsert] = field(default_factory=list)


class PgDumpParser:
    """Parser for PostgreSQL dump files."""

    # Regex patterns
    CREATE_TABLE_START = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
        r'(?:(?P<schema>\w+)\.)?(?:"?(?P<table>\w+)"?)\s*\(',
        re.IGNORECASE
    )

    INSERT_PATTERN = re.compile(
        r'INSERT\s+INTO\s+(?:(?P<schema>\w+)\.)?(?:"?(?P<table>\w+)"?)\s*'
        r'(?:\((?P<columns>[^)]+)\)\s+)?'
        r'VALUES\s*(?P<values>.+?);',
        re.IGNORECASE | re.DOTALL
    )

    COPY_PATTERN = re.compile(
        r'COPY\s+(?:(?P<schema>\w+)\.)?(?:"?(?P<table>\w+)"?)\s*'
        r'\((?P<columns>[^)]+)\)\s+FROM\s+stdin;',
        re.IGNORECASE
    )

    DATABASE_PATTERN = re.compile(
        r'\\connect\s+(?:"?(?P<dbname>\w+)"?)|'
        r'CREATE\s+DATABASE\s+(?:"?(?P<dbname2>\w+)"?)',
        re.IGNORECASE
    )

    COLUMN_PATTERN = re.compile(
        r'^\s*"?(?P<name>\w+)"?\s+(?P<type>[^,\n]+?)(?:,|$)',
        re.MULTILINE
    )

    def __init__(self):
        self.databases: List[ParsedDatabase] = []
        self.current_db_name: Optional[str] = None

    def parse(self, sql_content: str) -> List[ParsedDatabase]:
        """Parse SQL dump content and return list of databases.

        For single-database dumps (pg_dump), returns one database with
        a generated name based on tables.

        For multi-database dumps (pg_dumpall), returns multiple databases.
        """
        self.databases = []
        self.current_db_name = None

        # Check if this is a pg_dumpall (has database markers)
        db_matches = list(self.DATABASE_PATTERN.finditer(sql_content))

        if db_matches:
            # Multi-database dump
            self._parse_multi_db(sql_content, db_matches)
        else:
            # Single database dump
            self._parse_single_db(sql_content)

        return self.databases

    def _parse_single_db(self, sql_content: str) -> None:
        """Parse a single-database dump."""
        tables = self._extract_tables(sql_content)
        inserts = self._extract_inserts(sql_content)
        copy_inserts = self._extract_copy_statements(sql_content)
        inserts.extend(copy_inserts)

        if tables:
            # Generate database name from first table or use generic name
            db_name = self._generate_db_name(tables)
            self.databases.append(ParsedDatabase(
                name=db_name,
                tables=tables,
                inserts=inserts
            ))

    def _parse_multi_db(self, sql_content: str, db_matches: List) -> None:
        """Parse a multi-database dump (pg_dumpall)."""
        # Split content by database markers
        sections = []
        last_end = 0

        for match in db_matches:
            db_name = match.group("dbname") or match.group("dbname2")
            if not db_name or db_name.lower() in ("template0", "template1", "postgres"):
                continue

            start = match.end()
            if sections:
                sections[-1]["end"] = match.start()

            sections.append({
                "name": db_name,
                "start": start,
                "end": len(sql_content)
            })

        for section in sections:
            content = sql_content[section["start"]:section["end"]]
            tables = self._extract_tables(content)
            inserts = self._extract_inserts(content)
            copy_inserts = self._extract_copy_statements(content)
            inserts.extend(copy_inserts)

            if tables:
                self.databases.append(ParsedDatabase(
                    name=section["name"],
                    tables=tables,
                    inserts=inserts
                ))

    def _extract_tables(self, sql_content: str) -> List[ParsedTable]:
        """Extract CREATE TABLE statements."""
        tables = []

        for match in self.CREATE_TABLE_START.finditer(sql_content):
            schema = match.group("schema") or "public"
            table_name = match.group("table")

            # Find the matching closing parenthesis, handling nested parens
            start_pos = match.end()
            body, end_pos = self._extract_balanced_parens(sql_content, start_pos)

            if body is None:
                continue

            raw_sql = sql_content[match.start():end_pos]

            # Parse columns
            columns = self._parse_columns(body)
            constraints = self._parse_constraints(body)

            tables.append(ParsedTable(
                name=table_name,
                schema=schema,
                columns=columns,
                constraints=constraints,
                raw_sql=raw_sql
            ))

        return tables

    def _extract_balanced_parens(self, content: str, start: int) -> tuple:
        """Extract content within balanced parentheses starting from position.

        Returns (body_content, end_position) or (None, -1) if not found.
        """
        depth = 1
        pos = start
        in_string = False
        string_char = None

        while pos < len(content) and depth > 0:
            char = content[pos]

            if char in ("'", '"') and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                if pos + 1 < len(content) and content[pos + 1] == string_char:
                    pos += 1
                else:
                    in_string = False
                    string_char = None
            elif not in_string:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1

            pos += 1

        if depth == 0:
            return content[start:pos - 1], pos
        return None, -1

    def _parse_columns(self, body: str) -> List[Dict]:
        """Parse column definitions from CREATE TABLE body."""
        columns = []
        lines = self._smart_split_body(body)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip standalone constraints (not inline column constraints)
            upper_line = line.upper().lstrip()
            if upper_line.startswith(("CONSTRAINT ", "PRIMARY KEY (", "FOREIGN KEY (", "UNIQUE (", "CHECK (")):
                continue

            # Parse column definition
            # Remove leading/trailing quotes
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0].strip('"').strip("'")
                # Skip if col_name is a SQL keyword (indicates a constraint)
                if col_name.upper() in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "EXCLUDE"):
                    continue

                # Reconstruct type - handle types with parentheses like NUMERIC(10,2)
                col_type = parts[1]
                idx = 2
                # If type has opening paren without closing, grab more parts
                if '(' in col_type and ')' not in col_type:
                    while idx < len(parts):
                        col_type += parts[idx]
                        if ')' in parts[idx]:
                            idx += 1
                            break
                        idx += 1

                # Check for additional modifiers
                rest = " ".join(parts[idx:]).upper() if idx < len(parts) else ""
                full_upper = line.upper()

                is_pk = "PRIMARY KEY" in full_upper
                is_not_null = "NOT NULL" in full_upper
                has_default = "DEFAULT" in full_upper

                # Extract default value
                default_val = None
                if has_default:
                    default_match = re.search(r'DEFAULT\s+(.+?)(?:\s+(?:NOT\s+NULL|PRIMARY|UNIQUE|CHECK|REFERENCES|,|$))',
                                              line, re.IGNORECASE)
                    if default_match:
                        default_val = default_match.group(1).strip()

                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "is_primary_key": is_pk,
                    "is_not_null": is_not_null,
                    "default": default_val,
                    "raw": line
                })

        return columns

    def _smart_split_body(self, body: str) -> List[str]:
        """Split CREATE TABLE body by commas, respecting parentheses and quotes."""
        result = []
        current = ""
        depth = 0
        in_string = False
        quote_char = None

        for char in body:
            if char in ("'", '"') and not in_string:
                in_string = True
                quote_char = char
                current += char
            elif char == quote_char and in_string:
                in_string = False
                quote_char = None
                current += char
            elif char == '(' and not in_string:
                depth += 1
                current += char
            elif char == ')' and not in_string:
                depth -= 1
                current += char
            elif char == ',' and not in_string and depth == 0:
                result.append(current)
                current = ""
            else:
                current += char

        if current.strip():
            result.append(current)

        return result

    def _parse_constraints(self, body: str) -> List[str]:
        """Extract constraint definitions."""
        constraints = []
        lines = body.split(",")

        for line in lines:
            line = line.strip()
            if any(kw in line.upper() for kw in ["PRIMARY KEY (", "FOREIGN KEY", "CONSTRAINT"]):
                constraints.append(line)

        return constraints

    def _extract_inserts(self, sql_content: str) -> List[ParsedInsert]:
        """Extract INSERT statements."""
        inserts = []

        for match in self.INSERT_PATTERN.finditer(sql_content):
            table_name = match.group("table")
            columns_str = match.group("columns")
            values_str = match.group("values")

            columns = []
            if columns_str:
                columns = [c.strip().strip('"') for c in columns_str.split(",")]

            # Parse values - can have multiple value sets
            values = self._parse_values(values_str)

            inserts.append(ParsedInsert(
                table_name=table_name,
                columns=columns,
                values=values,
                raw_sql=match.group(0)
            ))

        return inserts

    def _extract_copy_statements(self, sql_content: str) -> List[ParsedInsert]:
        """Extract COPY statements and their data."""
        inserts = []

        # Find COPY statements
        copy_pattern = re.compile(
            r'COPY\s+(?:(?:\w+)\.)?(?:"?(\w+)"?)\s*\(([^)]+)\)\s+FROM\s+stdin;(.*?)\\.',
            re.IGNORECASE | re.DOTALL
        )

        for match in copy_pattern.finditer(sql_content):
            table_name = match.group(1)
            columns_str = match.group(2)
            data_block = match.group(3).strip()

            columns = [c.strip().strip('"') for c in columns_str.split(",")]

            # Parse tab-separated data
            values = []
            for line in data_block.split("\n"):
                line = line.strip()
                if line and line != "\\.":
                    row_values = tuple(
                        None if v == "\\N" else v
                        for v in line.split("\t")
                    )
                    values.append(row_values)

            if values:
                inserts.append(ParsedInsert(
                    table_name=table_name,
                    columns=columns,
                    values=values,
                    raw_sql=""
                ))

        return inserts

    def _parse_values(self, values_str: str) -> List[Tuple]:
        """Parse VALUES clause, handling multiple value sets."""
        values = []

        # Split by ),( for multiple value sets
        # This is a simplified parser - production would need more robust parsing
        value_sets = re.findall(r'\(([^)]+)\)', values_str)

        for vs in value_sets:
            # Parse individual values
            row_values = []
            # Simple split by comma (doesn't handle strings with commas)
            parts = self._smart_split(vs)
            for part in parts:
                part = part.strip()
                if part.upper() == "NULL":
                    row_values.append(None)
                elif part.startswith("'") and part.endswith("'"):
                    row_values.append(part[1:-1])
                else:
                    row_values.append(part)
            values.append(tuple(row_values))

        return values

    def _smart_split(self, s: str) -> List[str]:
        """Split by comma but respect quoted strings."""
        result = []
        current = ""
        in_quotes = False
        quote_char = None

        for char in s:
            if char in ("'", '"') and not in_quotes:
                in_quotes = True
                quote_char = char
                current += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current += char
            elif char == "," and not in_quotes:
                result.append(current)
                current = ""
            else:
                current += char

        if current:
            result.append(current)

        return result

    def _generate_db_name(self, tables: List[ParsedTable]) -> str:
        """Generate a database name from table names."""
        if not tables:
            return "imported_db"

        # Use first table name as base
        first_table = tables[0].name.lower()

        # Try to extract meaningful prefix
        if "_" in first_table:
            prefix = first_table.split("_")[0]
            return f"{prefix}_data"

        return f"{first_table}_db"
