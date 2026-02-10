"""In-memory schema cache - eliminates embedding API calls for schema retrieval."""
import sqlite3
import re
import logging
from typing import Dict, List, Optional
from backend.config import settings

logger = logging.getLogger("chatbot.sql.schema_cache")


# Keyword to table mapping for instant schema retrieval
KEYWORD_TABLE_MAP = {
    # Crew management
    "crew": ["crew_management.crew_members", "crew_management.crew_assignments", "crew_management.crew_roster"],
    "member": ["crew_management.crew_members"],
    "pilot": ["crew_management.crew_members"],
    "captain": ["crew_management.crew_members"],
    "first officer": ["crew_management.crew_members"],
    "purser": ["crew_management.crew_members"],
    "cabin": ["crew_management.crew_members"],
    "employee": ["crew_management.crew_members"],
    "qualification": ["crew_management.crew_qualifications"],
    "license": ["crew_management.crew_qualifications"],
    "rating": ["crew_management.crew_qualifications"],
    "medical": ["crew_management.crew_qualifications", "compliance_training.compliance_checks"],
    "assignment": ["crew_management.crew_assignments"],
    "duty": ["crew_management.crew_assignments", "crew_management.crew_rest_records"],
    "rest": ["crew_management.crew_rest_records"],
    "far 117": ["crew_management.crew_rest_records"],
    "fatigue": ["crew_management.crew_rest_records"],
    "document": ["crew_management.crew_documents"],
    "passport": ["crew_management.crew_documents", "crew_management.crew_members"],
    "visa": ["crew_management.crew_documents"],
    "contact": ["crew_management.crew_contacts"],
    "emergency": ["crew_management.crew_contacts"],
    "roster": ["crew_management.crew_roster"],
    "bid": ["crew_management.crew_roster"],
    "award": ["crew_management.crew_roster", "crew_management.crew_members"],
    "awarded": ["crew_management.crew_roster", "crew_management.crew_members"],
    "unawarded": ["crew_management.crew_roster", "crew_management.crew_members"],
    "unaward": ["crew_management.crew_roster", "crew_management.crew_members"],
    "not awarded": ["crew_management.crew_roster", "crew_management.crew_members"],
    "reserve": ["crew_management.crew_roster", "crew_management.crew_members"],
    "standby": ["crew_management.crew_roster", "crew_management.crew_members"],
    "roster_status": ["crew_management.crew_roster"],
    "month": ["crew_management.crew_roster"],
    "january": ["crew_management.crew_roster", "crew_management.crew_members"],
    "february": ["crew_management.crew_roster", "crew_management.crew_members"],
    "march": ["crew_management.crew_roster", "crew_management.crew_members"],
    "april": ["crew_management.crew_roster", "crew_management.crew_members"],
    "may": ["crew_management.crew_roster", "crew_management.crew_members"],
    "june": ["crew_management.crew_roster", "crew_management.crew_members"],
    "july": ["crew_management.crew_roster", "crew_management.crew_members"],
    "august": ["crew_management.crew_roster", "crew_management.crew_members"],
    "september": ["crew_management.crew_roster", "crew_management.crew_members"],
    "october": ["crew_management.crew_roster", "crew_management.crew_members"],
    "november": ["crew_management.crew_roster", "crew_management.crew_members"],
    "december": ["crew_management.crew_roster", "crew_management.crew_members"],
    "seniority": ["crew_management.crew_roster", "crew_management.crew_members"],
    "bid preference": ["crew_management.crew_roster"],
    "duty type": ["crew_management.crew_roster"],
    "flight hours": ["crew_management.crew_roster", "hr_payroll.payroll_records"],
    "block hours": ["crew_management.crew_roster"],

    # Flight operations
    "flight": ["flight_operations.flights", "crew_management.crew_assignments"],
    "schedule": ["flight_operations.flights", "crew_management.crew_assignments"],
    "aircraft": ["flight_operations.aircraft"],
    "plane": ["flight_operations.aircraft"],
    "airport": ["flight_operations.airports"],
    "hub": ["flight_operations.airports"],
    "pairing": ["flight_operations.crew_pairings", "flight_operations.pairing_flights"],
    "leg": ["flight_operations.flight_legs"],
    "delay": ["flight_operations.flights", "flight_operations.disruptions"],
    "cancel": ["flight_operations.flights", "flight_operations.disruptions"],
    "disruption": ["flight_operations.disruptions"],
    "irregular": ["flight_operations.disruptions"],
    "hotel": ["flight_operations.hotels"],
    "layover": ["flight_operations.hotels"],

    # HR/Payroll
    "pay": ["hr_payroll.payroll_records", "hr_payroll.pay_grades"],
    "salary": ["hr_payroll.payroll_records", "hr_payroll.pay_grades"],
    "payroll": ["hr_payroll.payroll_records"],
    "wage": ["hr_payroll.payroll_records"],
    "grade": ["hr_payroll.pay_grades"],
    "leave": ["hr_payroll.leave_records", "hr_payroll.leave_balances"],
    "vacation": ["hr_payroll.leave_records", "hr_payroll.leave_balances"],
    "sick": ["hr_payroll.leave_records"],
    "benefit": ["hr_payroll.benefits"],
    "insurance": ["hr_payroll.benefits"],
    "401k": ["hr_payroll.benefits"],
    "performance": ["hr_payroll.performance_reviews"],
    "review": ["hr_payroll.performance_reviews"],
    "expense": ["hr_payroll.expense_claims"],
    "reimbursement": ["hr_payroll.expense_claims"],

    # Compliance/Training
    "training": ["compliance_training.training_records", "compliance_training.training_courses", "compliance_training.training_schedules"],
    "course": ["compliance_training.training_courses"],
    "recurrent": ["compliance_training.training_courses", "compliance_training.training_records"],
    "certification": ["compliance_training.training_records"],
    "enrollment": ["compliance_training.training_enrollments"],
    "compliance": ["compliance_training.compliance_checks"],
    "check": ["compliance_training.compliance_checks"],
    "proficiency": ["compliance_training.compliance_checks"],
    "safety": ["compliance_training.safety_incidents"],
    "incident": ["compliance_training.safety_incidents"],
    "audit": ["compliance_training.audit_logs"],

    # Cross-database / cross-domain keywords
    "who": ["crew_management.crew_members"],
    "name": ["crew_management.crew_members"],
    "names": ["crew_management.crew_members"],
    "list": ["crew_management.crew_members"],
    "show": ["crew_management.crew_members"],
    "all crew": ["crew_management.crew_members"],
    "active": ["crew_management.crew_members"],
    "base": ["crew_management.crew_members", "flight_operations.airports"],
    "role": ["crew_management.crew_members", "hr_payroll.pay_grades"],
    "status": ["crew_management.crew_members"],
    "score": ["compliance_training.training_records"],
    "rating": ["hr_payroll.performance_reviews", "crew_management.crew_qualifications"],
    "overdue": ["compliance_training.compliance_checks"],
    "expired": ["crew_management.crew_qualifications"],
    "expiring": ["crew_management.crew_qualifications"],
    "reason": ["crew_management.crew_roster"],
}

# Full schema cache loaded from database
_schema_cache: Optional[Dict[str, Dict]] = None


def _load_schema_cache() -> Dict[str, Dict]:
    """Load all schema metadata from app.db into memory."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    _schema_cache = {}
    try:
        conn = sqlite3.connect(settings.app_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT db_name, table_name, column_details, row_count, ddl_statement, llm_description, column_descriptions
            FROM schema_metadata
        """)

        for row in cursor.fetchall():
            full_name = f"{row['db_name']}.{row['table_name']}"
            # Parse column descriptions if available
            col_descriptions = {}
            if row['column_descriptions']:
                try:
                    import json
                    col_descriptions = json.loads(row['column_descriptions'])
                except (json.JSONDecodeError, TypeError):
                    pass
            _schema_cache[full_name] = {
                "db_name": row['db_name'],
                "table_name": row['table_name'],
                "description": row['llm_description'],
                "columns": _parse_columns(row['column_details'], row['ddl_statement']),
                "column_descriptions": col_descriptions,
                "ddl": row['ddl_statement'],
                "row_count": row['row_count']
            }
        conn.close()
        logger.info(f"Schema cache loaded: {len(_schema_cache)} tables from {settings.app_db_path}")
        if _schema_cache:
            db_names = set(v["db_name"] for v in _schema_cache.values())
            logger.info(f"Schema cache databases: {db_names}")
        else:
            logger.warning(f"Schema cache is EMPTY - schema_metadata table has no rows in {settings.app_db_path}")
    except Exception as e:
        logger.error(f"Error loading schema cache from {settings.app_db_path}: {e}")
        _schema_cache = {}

    return _schema_cache


def reload_cache():
    """Clear and reload the schema cache."""
    global _schema_cache
    _schema_cache = None
    _load_schema_cache()


def _parse_columns(column_details: str, ddl: str) -> List[Dict]:
    """Parse column details string into structured format."""
    columns = []
    if not column_details:
        return columns

    # Parse "col_name (TYPE), col_name2 (TYPE2)" format
    for col in column_details.split(", "):
        match = re.match(r'(\w+)\s*\(([^)]+)\)', col.strip())
        if match:
            name, col_type = match.groups()
            is_pk = "PRIMARY KEY" in ddl and name in ddl.split("PRIMARY KEY")[0].split(",")[-1] if ddl else False
            columns.append({
                "name": name,
                "type": col_type,
                "primary_key": is_pk or name in ("id", "crew_id", "employee_id")
            })
    return columns


def _match_uploaded_schemas(query_lower: str, cache: Dict[str, Dict]) -> set:
    """Match query keywords against uploaded/dynamic database schemas.

    Scans table names, column names, and descriptions of databases that are
    NOT in the hardcoded KEYWORD_TABLE_MAP.  This ensures uploaded databases
    are discoverable without manual keyword mapping.
    """
    hardcoded_dbs = {"crew_management", "flight_operations", "hr_payroll", "compliance_training"}
    matched = set()

    query_words = set(re.findall(r'[a-z0-9]+', query_lower))

    for full_name, schema in cache.items():
        db_name = schema.get("db_name", "")
        if db_name in hardcoded_dbs or db_name == "app":
            continue

        table_name = schema.get("table_name", "").lower()
        description = (schema.get("description") or "").lower()

        # Match against table name (split underscores)
        table_words = set(table_name.replace("_", " ").split())
        if query_words & table_words:
            matched.add(full_name)
            continue

        # Match against column names
        for col in schema.get("columns", []):
            col_name = col.get("name", "").lower()
            col_words = set(col_name.replace("_", " ").split())
            if query_words & col_words:
                matched.add(full_name)
                break

        # Match against LLM-generated description
        if any(w in description for w in query_words if len(w) > 2):
            matched.add(full_name)
            continue

        # Match against column descriptions
        col_descriptions = schema.get("column_descriptions", {})
        if col_descriptions:
            all_desc_text = " ".join(str(v).lower() for v in col_descriptions.values())
            if any(w in all_desc_text for w in query_words if len(w) > 2):
                matched.add(full_name)

    return matched


def get_schemas_by_keywords(query: str, max_tables: int = 6) -> List[Dict]:
    """Get relevant schemas using keyword matching - NO API CALLS.

    Uses the hardcoded KEYWORD_TABLE_MAP for the 4 internal databases,
    then dynamically matches uploaded database schemas by table/column
    names and descriptions.
    """
    cache = _load_schema_cache()
    if not cache:
        return []

    query_lower = query.lower()
    matched_tables = set()

    # Stage 1: Hardcoded keyword matching (fast, for internal DBs)
    for keyword, tables in KEYWORD_TABLE_MAP.items():
        if keyword in query_lower:
            matched_tables.update(tables)

    # Stage 2: Dynamic matching for uploaded databases
    uploaded_matches = _match_uploaded_schemas(query_lower, cache)
    matched_tables.update(uploaded_matches)

    # If no keyword matches at all, return most common internal tables
    # PLUS any uploaded tables that have employee-like columns
    if not matched_tables:
        matched_tables = {
            "crew_management.crew_members",
            "crew_management.crew_assignments",
            "flight_operations.flights"
        }
        # Also include uploaded tables with employee_id columns
        for full_name, schema in cache.items():
            if schema.get("db_name") in {"crew_management", "flight_operations",
                                          "hr_payroll", "compliance_training", "app"}:
                continue
            col_names = [c.get("name", "").lower() for c in schema.get("columns", [])]
            if "employee_id" in col_names or "emp_id" in col_names or "id" in col_names:
                matched_tables.add(full_name)

    # Build result list
    results = []
    for table_name in matched_tables:
        if table_name in cache:
            results.append(cache[table_name])

    # Limit results
    return results[:max_tables]


def get_all_schemas() -> List[Dict]:
    """Get all schemas from cache."""
    cache = _load_schema_cache()
    return list(cache.values())


def clear_cache():
    """Clear the schema cache (for testing/reload)."""
    global _schema_cache
    _schema_cache = None
