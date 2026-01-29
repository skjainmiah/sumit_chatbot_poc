"""Database Registry - centralized management of database connections and visibility."""
import sqlite3
import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from backend.config import settings


class DatabaseRegistry:
    """Singleton for managing database registry.

    Replaces static DB_MAPPING with dynamic registry that supports:
    - Visibility toggling for chat queries
    - Uploaded databases from SQL dumps
    - Centralized database path management
    """

    _instance = None
    _cache = None
    _cache_time = 0
    _cache_ttl = 5  # seconds

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        """Get connection to app.db."""
        conn = sqlite3.connect(settings.app_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _refresh_cache(self) -> None:
        """Refresh the database cache from app.db."""
        import time
        current_time = time.time()

        if self._cache is not None and (current_time - self._cache_time) < self._cache_ttl:
            return

        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT db_id, db_name, db_path, display_name, description,
                       source_type, is_visible, is_system, upload_filename,
                       uploaded_by, table_count, created_at
                FROM database_registry
                ORDER BY db_id
            """)
            self._cache = {row["db_name"]: dict(row) for row in cursor.fetchall()}
            self._cache_time = current_time
        except sqlite3.OperationalError:
            # Table doesn't exist yet (first run)
            self._cache = {}
        finally:
            conn.close()

    def invalidate_cache(self) -> None:
        """Force cache refresh on next access."""
        self._cache = None
        self._cache_time = 0

    def get_all_databases(self) -> Dict[str, Dict]:
        """Get all registered databases."""
        self._refresh_cache()
        return self._cache.copy()

    def get_visible_databases(self) -> Dict[str, str]:
        """Get visible databases as {db_name: db_path} mapping.

        This replaces the static DB_MAPPING for query execution.
        """
        self._refresh_cache()
        return {
            name: info["db_path"]
            for name, info in self._cache.items()
            if info["is_visible"] and name != "app"
        }

    def get_all_db_mapping(self) -> Dict[str, str]:
        """Get all databases as {db_name: db_path} mapping (excluding app).

        Use this for operations that need all databases regardless of visibility.
        """
        self._refresh_cache()
        return {
            name: info["db_path"]
            for name, info in self._cache.items()
            if name != "app"
        }

    def get_database_info(self, db_name: str) -> Optional[Dict]:
        """Get info for a specific database."""
        self._refresh_cache()
        return self._cache.get(db_name)

    def get_database_path(self, db_name: str) -> Optional[str]:
        """Get path for a specific database."""
        info = self.get_database_info(db_name)
        return info["db_path"] if info else None

    def is_visible(self, db_name: str) -> bool:
        """Check if a database is visible."""
        info = self.get_database_info(db_name)
        return bool(info and info["is_visible"])

    def set_visibility(self, db_name: str, visible: bool) -> bool:
        """Set database visibility. Returns True if successful."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "UPDATE database_registry SET is_visible = ? WHERE db_name = ?",
                (1 if visible else 0, db_name)
            )
            conn.commit()
            self.invalidate_cache()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def register_database(
        self,
        db_name: str,
        db_path: str,
        display_name: str = None,
        description: str = None,
        source_type: str = "uploaded",
        is_visible: bool = True,
        upload_filename: str = None,
        uploaded_by: int = None,
        table_count: int = 0
    ) -> int:
        """Register a new database. Returns db_id."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO database_registry
                (db_name, db_path, display_name, description, source_type,
                 is_visible, is_system, upload_filename, uploaded_by, table_count)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """, (db_name, db_path, display_name or db_name, description,
                  source_type, 1 if is_visible else 0, upload_filename,
                  uploaded_by, table_count))
            conn.commit()
            self.invalidate_cache()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_database(self, db_name: str, **kwargs) -> bool:
        """Update database info. Returns True if successful."""
        if not kwargs:
            return False

        allowed_fields = {"display_name", "description", "is_visible", "table_count"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [db_name]

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                f"UPDATE database_registry SET {set_clause} WHERE db_name = ?",
                values
            )
            conn.commit()
            self.invalidate_cache()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def unregister_database(self, db_name: str) -> bool:
        """Remove a database from registry. Returns True if successful.

        Note: Does not delete the actual database file.
        """
        # Prevent deletion of mock databases
        info = self.get_database_info(db_name)
        if info and info["source_type"] == "mock":
            return False

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM database_registry WHERE db_name = ? AND source_type != 'mock'",
                (db_name,)
            )
            conn.commit()
            self.invalidate_cache()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_uploaded_database(self, db_name: str) -> bool:
        """Delete an uploaded database (both registry entry and file).

        Returns True if successful. Mock databases cannot be deleted.
        """
        info = self.get_database_info(db_name)
        if not info or info["source_type"] == "mock":
            return False

        db_path = info["db_path"]

        # Remove from registry first
        if not self.unregister_database(db_name):
            return False

        # Delete the actual file
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except OSError:
            pass  # File deletion failed but registry is updated

        return True

    def get_visible_count(self) -> int:
        """Get count of visible databases."""
        self._refresh_cache()
        return sum(1 for info in self._cache.values()
                   if info["is_visible"] and info["db_name"] != "app")


# Singleton accessor
_registry: Optional[DatabaseRegistry] = None


def get_database_registry() -> DatabaseRegistry:
    """Get database registry singleton."""
    global _registry
    if _registry is None:
        _registry = DatabaseRegistry()
    return _registry


# Backward-compatible helpers that use registry
def get_db_mapping() -> Dict[str, str]:
    """Get visible databases mapping (backward compatible with old DB_MAPPING usage)."""
    return get_database_registry().get_visible_databases()


def get_all_db_mapping() -> Dict[str, str]:
    """Get all databases mapping regardless of visibility."""
    return get_database_registry().get_all_db_mapping()
