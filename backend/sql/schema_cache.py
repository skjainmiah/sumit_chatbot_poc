"""In-memory schema cache - eliminates embedding API calls for schema retrieval."""
import sqlite3
import re
from typing import Dict, List, Optional
from backend.config import settings
from backend.db.registry import get_database_registry


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
    """Load schema metadata from app.db into memory, filtered by visible databases."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    _schema_cache = {}
    try:
        # Get visible database names from registry
        try:
            registry = get_database_registry()
            visible_db_names = list(registry.get_visible_databases().keys())
        except Exception:
            visible_db_names = []

        conn = sqlite3.connect(settings.app_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if visible_db_names:
            placeholders = ",".join("?" * len(visible_db_names))
            cursor.execute(f"""
                SELECT db_name, table_name, column_details, row_count, ddl_statement, llm_description
                FROM schema_metadata
                WHERE db_name IN ({placeholders})
            """, visible_db_names)
        else:
            cursor.execute("""
                SELECT db_name, table_name, column_details, row_count, ddl_statement, llm_description
                FROM schema_metadata
            """)

        for row in cursor.fetchall():
            full_name = f"{row['db_name']}.{row['table_name']}"
            _schema_cache[full_name] = {
                "db_name": row['db_name'],
                "table_name": row['table_name'],
                "description": row['llm_description'],
                "columns": _parse_columns(row['column_details'], row['ddl_statement']),
                "ddl": row['ddl_statement'],
                "row_count": row['row_count']
            }
        conn.close()
        print(f"Schema cache loaded: {len(_schema_cache)} tables (visible only)")
    except Exception as e:
        print(f"Error loading schema cache: {e}")
        _schema_cache = {}

    return _schema_cache


def reload_cache():
    """Clear and reload the schema cache. Call when visibility changes."""
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


def get_schemas_by_keywords(query: str, max_tables: int = 6) -> List[Dict]:
    """Get relevant schemas using keyword matching - NO API CALLS."""
    cache = _load_schema_cache()
    if not cache:
        return []

    query_lower = query.lower()
    matched_tables = set()

    # Match keywords to tables
    for keyword, tables in KEYWORD_TABLE_MAP.items():
        if keyword in query_lower:
            matched_tables.update(tables)

    # If no keyword matches, return most common tables for general queries
    if not matched_tables:
        matched_tables = {
            "crew_management.crew_members",
            "crew_management.crew_assignments",
            "flight_operations.flights"
        }

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
