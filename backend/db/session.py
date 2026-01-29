"""SQLite database session management."""
import sqlite3
from contextlib import contextmanager
from typing import Generator, Dict
from backend.config import settings


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Get a SQLite connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_crew_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for crew_management database."""
    conn = get_db_connection(settings.crew_db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_flight_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for flight_operations database."""
    conn = get_db_connection(settings.flight_db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_hr_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for hr_payroll database."""
    conn = get_db_connection(settings.hr_db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_compliance_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for compliance_training database."""
    conn = get_db_connection(settings.compliance_db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_app_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for app database."""
    conn = get_db_connection(settings.app_db_path)
    try:
        yield conn
    finally:
        conn.close()


def execute_query(db_path: str, query: str, params: tuple = ()) -> list:
    """Execute a read query and return results as list of dicts."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute_write(db_path: str, query: str, params: tuple = ()) -> int:
    """Execute a write query and return lastrowid."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _get_db_mapping_from_registry() -> Dict[str, str]:
    """Get database mapping from registry. Falls back to static config if registry unavailable."""
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        mapping = registry.get_visible_databases()
        if mapping:
            # Add app database
            mapping["app"] = settings.app_db_path
            return mapping
    except Exception:
        pass

    # Fallback to static mapping
    return {
        'crew_management': settings.crew_db_path,
        'flight_operations': settings.flight_db_path,
        'hr_payroll': settings.hr_db_path,
        'compliance_training': settings.compliance_db_path,
        'app': settings.app_db_path,
    }


# Database mapping for multi-db queries (backward compatible, now uses registry)
@property
def _db_mapping():
    return _get_db_mapping_from_registry()


# Static fallback for imports that need DB_MAPPING at module level
DB_MAPPING = {
    'crew_management': settings.crew_db_path,
    'flight_operations': settings.flight_db_path,
    'hr_payroll': settings.hr_db_path,
    'compliance_training': settings.compliance_db_path,
    'app': settings.app_db_path,
}


def get_db_path_by_name(db_name: str) -> str:
    """Get database path by name."""
    mapping = _get_db_mapping_from_registry()
    if db_name not in mapping:
        # Try to match partial names
        for key in mapping:
            if db_name.lower() in key.lower():
                return mapping[key]
        raise ValueError(f"Unknown database: {db_name}")
    return mapping[db_name]


def get_multi_db_connection(visible_only: bool = True) -> sqlite3.Connection:
    """Get a connection with operational databases ATTACHed.

    This enables cross-database JOINs using the syntax:
        SELECT * FROM crew_management.crew_members cm
        JOIN hr_payroll.payroll_records pr ON cm.employee_id = pr.employee_id

    Args:
        visible_only: If True, only attach visible databases from registry.
                     If False, attach all databases.

    All databases are attached by their logical name:
        crew_management, flight_operations, hr_payroll, compliance_training, etc.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Get database mapping based on visibility setting
    if visible_only:
        try:
            from backend.db.registry import get_database_registry
            registry = get_database_registry()
            db_mapping = registry.get_visible_databases()
        except Exception:
            db_mapping = {k: v for k, v in DB_MAPPING.items() if k != "app"}
    else:
        try:
            from backend.db.registry import get_database_registry
            registry = get_database_registry()
            db_mapping = registry.get_all_db_mapping()
        except Exception:
            db_mapping = {k: v for k, v in DB_MAPPING.items() if k != "app"}

    for db_name, db_path in db_mapping.items():
        if db_name == "app":
            continue
        try:
            conn.execute(f"ATTACH DATABASE ? AS [{db_name}]", (db_path,))
        except sqlite3.Error:
            pass  # Skip databases that can't be attached

    return conn


def execute_multi_db_query(query: str, params: tuple = ()) -> list:
    """Execute a read query across all attached databases. Returns list of dicts."""
    conn = get_multi_db_connection()
    try:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
