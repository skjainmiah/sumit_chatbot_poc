"""Microsoft SQL Server dump file parser.

Parses MSSQL scripts to extract:
- Database names (from USE statements)
- CREATE TABLE statements
- INSERT statements
"""
import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedTable:
    """Represents a parsed CREATE TABLE statement."""
    name: str
    schema: str = "dbo"
    columns: List[Dict] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    raw_sql: str = ""


@dataclass
class ParsedInsert:
    """Represents a parsed INSERT statement."""
    table_name: str
    columns: List[str] = field(default_factory=list)
    values: List[tuple] = field(default_factory=list)
    raw_sql: str = ""


@dataclass
class ParsedDatabase:
    """Represents a parsed database."""
    name: str
    tables: List[ParsedTable] = field(default_factory=list)
    inserts: List[ParsedInsert] = field(default_factory=list)


class MssqlDumpParser:
    """Parser for Microsoft SQL Server dump files."""

    # Note: CREATE_TABLE_PATTERN uses a simpler approach - we'll extract body differently
    CREATE_TABLE_START = re.compile(
        r'CREATE\s+TABLE\s+(?:\[?(?P<schema>\w+)\]?\.)?\[?(?P<table>\w+)\]?\s*\(',
        re.IGNORECASE
    )

    INSERT_PATTERN = re.compile(
        r'INSERT\s+(?:INTO\s+)?(?:\[?(?P<schema>\w+)\]?\.)?\[?(?P<table>\w+)\]?\s*'
        r'(?:\((?P<columns>[^)]+)\)\s+)?'
        r'VALUES\s*(?P<values>.+?)(?:;|$|(?=INSERT))',
        re.IGNORECASE | re.DOTALL
    )

    USE_DATABASE_PATTERN = re.compile(
        r'USE\s+\[?(?P<dbname>\w+)\]?',
        re.IGNORECASE
    )

    CREATE_DATABASE_PATTERN = re.compile(
        r'CREATE\s+DATABASE\s+\[?(?P<dbname>\w+)\]?',
        re.IGNORECASE
    )

    # Pattern to remove GO statements
    GO_PATTERN = re.compile(r'^\s*GO\s*$', re.MULTILINE | re.IGNORECASE)

    # Pattern to remove comments
    COMMENT_PATTERN = re.compile(r'--[^\n]*|/\*.*?\*/', re.DOTALL)

    def __init__(self):
        self.databases: List[ParsedDatabase] = []
        self.current_db_name: Optional[str] = None

    def parse(self, sql_content: str) -> List[ParsedDatabase]:
        """Parse MSSQL script content and return list of databases."""
        self.databases = []
        self.current_db_name = None

        # Pre-process: remove comments and GO statements
        sql_content = self.COMMENT_PATTERN.sub('', sql_content)
        sql_content = self.GO_PATTERN.sub('', sql_content)

        # Check for USE statements (indicates multi-database or named database)
        use_matches = list(self.USE_DATABASE_PATTERN.finditer(sql_content))
        create_db_matches = list(self.CREATE_DATABASE_PATTERN.finditer(sql_content))

        if use_matches or create_db_matches:
            self._parse_multi_db(sql_content, use_matches)
        else:
            self._parse_single_db(sql_content)

        return self.databases

    def _parse_single_db(self, sql_content: str) -> None:
        """Parse a single-database script."""
        tables = self._extract_tables(sql_content)
        inserts = self._extract_inserts(sql_content)

        if tables:
            db_name = self._generate_db_name(tables)
            self.databases.append(ParsedDatabase(
                name=db_name,
                tables=tables,
                inserts=inserts
            ))

    def _parse_multi_db(self, sql_content: str, use_matches: List) -> None:
        """Parse a multi-database script."""
        if not use_matches:
            self._parse_single_db(sql_content)
            return

        # Split content by USE statements
        sections = []
        last_end = 0

        for match in use_matches:
            db_name = match.group("dbname")
            # Skip system databases
            if db_name.lower() in ("master", "tempdb", "model", "msdb"):
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
            schema = match.group("schema") or "dbo"
            table_name = match.group("table")

            # Skip temporary tables
            if table_name.startswith("#"):
                continue

            # Find the matching closing parenthesis, handling nested parens
            start_pos = match.end()
            body, end_pos = self._extract_balanced_parens(sql_content, start_pos)

            if body is None:
                continue

            raw_sql = sql_content[match.start():end_pos]
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
        depth = 1  # We're already past the opening paren
        pos = start
        in_string = False
        string_char = None

        while pos < len(content) and depth > 0:
            char = content[pos]

            # Handle string literals
            if char in ("'", '"') and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                # Check for escaped quote
                if pos + 1 < len(content) and content[pos + 1] == string_char:
                    pos += 1  # Skip escaped quote
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
            # pos is now at the character after the closing paren
            return content[start:pos - 1], pos
        return None, -1

    def _parse_columns(self, body: str) -> List[Dict]:
        """Parse column definitions from CREATE TABLE body."""
        columns = []

        # Split by comma, but respect parentheses
        parts = self._smart_split(body, ',')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Skip constraints
            upper_part = part.upper()
            if any(kw in upper_part for kw in [
                "PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK",
                "CONSTRAINT", "INDEX", "CLUSTERED", "NONCLUSTERED"
            ]):
                continue

            # Parse column definition
            # Remove brackets from column name
            part = re.sub(r'\[(\w+)\]', r'\1', part)
            tokens = part.split()

            if len(tokens) >= 2:
                col_name = tokens[0]
                col_type = tokens[1]

                # Handle type with size like VARCHAR(255) or DECIMAL(10,2)
                if '(' in col_type or (len(tokens) > 2 and tokens[2].startswith('(')):
                    type_match = re.match(r'(\w+)(\([^)]+\))?', ' '.join(tokens[1:3]))
                    if type_match:
                        col_type = type_match.group(0)

                # Check for modifiers
                is_pk = "PRIMARY KEY" in upper_part
                is_identity = "IDENTITY" in upper_part
                is_not_null = "NOT NULL" in upper_part
                has_default = "DEFAULT" in upper_part

                # Extract default value
                default_val = None
                if has_default:
                    default_match = re.search(
                        r'DEFAULT\s+(\([^)]+\)|\'[^\']*\'|[\w.]+)',
                        part, re.IGNORECASE
                    )
                    if default_match:
                        default_val = default_match.group(1)

                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "is_primary_key": is_pk,
                    "is_identity": is_identity,
                    "is_not_null": is_not_null,
                    "default": default_val,
                    "raw": part
                })

        return columns

    def _parse_constraints(self, body: str) -> List[str]:
        """Extract constraint definitions."""
        constraints = []
        parts = self._smart_split(body, ',')

        for part in parts:
            part = part.strip()
            upper_part = part.upper()
            if any(kw in upper_part for kw in ["PRIMARY KEY", "FOREIGN KEY", "CONSTRAINT", "UNIQUE"]):
                constraints.append(part)

        return constraints

    def _extract_inserts(self, sql_content: str) -> List[ParsedInsert]:
        """Extract INSERT statements."""
        inserts = []

        for match in self.INSERT_PATTERN.finditer(sql_content):
            table_name = match.group("table")
            columns_str = match.group("columns")
            values_str = match.group("values")

            # Clean up table name (remove brackets)
            table_name = table_name.strip("[]")

            columns = []
            if columns_str:
                columns = [c.strip().strip("[]") for c in columns_str.split(",")]

            values = self._parse_values(values_str)

            if values:
                inserts.append(ParsedInsert(
                    table_name=table_name,
                    columns=columns,
                    values=values,
                    raw_sql=match.group(0)
                ))

        return inserts

    def _parse_values(self, values_str: str) -> List[tuple]:
        """Parse VALUES clause."""
        values = []

        # Find all value sets (...)
        value_sets = re.findall(r'\(([^)]+)\)', values_str)

        for vs in value_sets:
            row_values = []
            parts = self._smart_split(vs, ',')

            for part in parts:
                part = part.strip()
                if part.upper() == "NULL":
                    row_values.append(None)
                elif part.startswith("N'") and part.endswith("'"):
                    # Unicode string literal
                    row_values.append(part[2:-1])
                elif part.startswith("'") and part.endswith("'"):
                    row_values.append(part[1:-1])
                else:
                    row_values.append(part)

            values.append(tuple(row_values))

        return values

    def _smart_split(self, s: str, delimiter: str = ',') -> List[str]:
        """Split by delimiter but respect quoted strings and parentheses."""
        result = []
        current = ""
        depth = 0
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
            elif char == '(' and not in_quotes:
                depth += 1
                current += char
            elif char == ')' and not in_quotes:
                depth -= 1
                current += char
            elif char == delimiter and not in_quotes and depth == 0:
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
            return "imported_mssql_db"

        first_table = tables[0].name.lower()

        if "_" in first_table:
            prefix = first_table.split("_")[0]
            return f"{prefix}_data"

        return f"{first_table}_db"
