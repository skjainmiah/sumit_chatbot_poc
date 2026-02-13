"""Column-level PII masking for query results.

Allows admins to mark specific database columns as sensitive.
When a query returns data from masked columns, values are replaced
with [MASKED] before being shown to the user or sent to the LLM.
"""
import re
import sqlite3
import logging
from typing import Dict, Set, List, Any, Optional

from backend.config import settings

logger = logging.getLogger("chatbot.pii.column")

MASK_TOKEN = "[MASKED]"


def _ensure_column_masks_table():
    """Create the pii_column_masks table if it doesn't exist."""
    conn = sqlite3.connect(settings.app_db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pii_column_masks (
            db_name    TEXT NOT NULL,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            enabled    INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (db_name, table_name, column_name)
        )
    """)
    conn.commit()
    conn.close()


def get_masked_columns() -> Dict[str, Set[str]]:
    """Load enabled column masks from DB.

    Returns:
        Dict mapping "db_name.table_name" to a set of masked column names.
        Example: {"mydb.employees": {"FirstName", "LastName"}}
    """
    _ensure_column_masks_table()
    conn = sqlite3.connect(settings.app_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT db_name, table_name, column_name FROM pii_column_masks WHERE enabled = 1"
    ).fetchall()
    conn.close()

    masks: Dict[str, Set[str]] = {}
    for r in rows:
        key = f"{r['db_name']}.{r['table_name']}"
        masks.setdefault(key, set()).add(r["column_name"].lower())
    return masks


def save_column_masks(masks: List[Dict[str, Any]]):
    """Upsert column mask configurations.

    Args:
        masks: List of dicts with keys: db_name, table_name, column_name, enabled
    """
    _ensure_column_masks_table()
    conn = sqlite3.connect(settings.app_db_path)
    for m in masks:
        conn.execute("""
            INSERT INTO pii_column_masks (db_name, table_name, column_name, enabled)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(db_name, table_name, column_name)
            DO UPDATE SET enabled = excluded.enabled
        """, (m["db_name"], m["table_name"], m["column_name"], int(m["enabled"])))
    conn.commit()
    conn.close()


def get_column_mask_settings() -> List[Dict[str, Any]]:
    """Return all mask configs grouped for the API response."""
    _ensure_column_masks_table()
    conn = sqlite3.connect(settings.app_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT db_name, table_name, column_name, enabled FROM pii_column_masks ORDER BY db_name, table_name, column_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def parse_column_aliases(sql: str) -> Dict[str, str]:
    """Extract column aliases from a SQL SELECT clause.

    Parses patterns like:
      - col AS alias
      - col as alias
      - table.col AS alias

    Returns:
        Dict mapping lowercase alias -> lowercase source column name.
    """
    aliases: Dict[str, str] = {}
    # Find the SELECT ... FROM portion
    match = re.search(r'SELECT\s+(.*?)\s+FROM\s', sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return aliases

    select_clause = match.group(1)
    # Split on commas (but not commas inside parentheses)
    depth = 0
    parts: List[str] = []
    current: List[str] = []
    for ch in select_clause:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        parts.append(''.join(current).strip())

    for part in parts:
        # Match: something AS alias
        m = re.match(r'(.+?)\s+[Aa][Ss]\s+["\[]?(\w+)["\]]?\s*$', part.strip())
        if m:
            source = m.group(1).strip()
            alias = m.group(2).strip()
            # Extract just the column name from table.col
            if '.' in source:
                source = source.rsplit('.', 1)[1]
            # Strip quotes/brackets
            source = source.strip('`"[]')
            aliases[alias.lower()] = source.lower()

    return aliases


def mask_query_results(results: Dict[str, Any], sql: str) -> Dict[str, Any]:
    """Mask values in query results for columns configured as sensitive.

    Args:
        results: Dict with keys "columns" (list[str]), "rows" (list[dict]), "row_count" (int)
        sql: The executed SQL string (used to resolve aliases)

    Returns:
        The results dict with masked values replaced by MASK_TOKEN.
    """
    if not results or not results.get("rows"):
        return results

    masked_cols_config = get_masked_columns()
    if not masked_cols_config:
        return results

    # Build a flat set of all masked column names (lowercase)
    all_masked: Set[str] = set()
    for col_set in masked_cols_config.values():
        all_masked.update(col_set)

    if not all_masked:
        return results

    # Parse aliases so "FirstName AS fn" still gets masked
    aliases = parse_column_aliases(sql)

    # Determine which result columns need masking
    columns_to_mask: Set[str] = set()
    for col in results.get("columns", []):
        col_lower = col.lower()
        if col_lower in all_masked:
            columns_to_mask.add(col)
        elif aliases.get(col_lower) in all_masked:
            columns_to_mask.add(col)

    if not columns_to_mask:
        return results

    logger.info(f"[column_mask] Masking columns: {columns_to_mask}")

    # Replace values
    for row in results["rows"]:
        for col in columns_to_mask:
            if col in row:
                row[col] = MASK_TOKEN

    return results
