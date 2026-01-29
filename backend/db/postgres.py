"""PostgreSQL database connection and query execution."""

import os
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2 import pool
except ImportError:
    raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")


class PostgreSQLConnection:
    """PostgreSQL connection manager with connection pooling."""

    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pool is None:
            self._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv("PGHOST", "localhost"),
                port=int(os.getenv("PGPORT", "5432")),
                user=os.getenv("PGUSER", "postgres"),
                password=os.getenv("PGPASSWORD", ""),
                database=os.getenv("PGDATABASE", "postgres"),
                sslmode=os.getenv("PGSSLMODE", "prefer")
            )
            print(f"PostgreSQL pool initialized: {os.getenv('PGHOST', 'localhost')}:{os.getenv('PGPORT', '5432')}")

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """Get a cursor from a pooled connection."""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

    def execute_query(
        self,
        sql: str,
        params: tuple = None,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """Execute a SELECT query and return results."""
        with self.get_cursor() as cursor:
            # Set statement timeout
            cursor.execute(f"SET statement_timeout = '{timeout_seconds * 1000}'")

            # Execute query
            cursor.execute(sql, params)

            # Get results
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            return {
                "columns": columns,
                "rows": [dict(row) for row in rows],
                "row_count": len(rows)
            }

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False

    def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            PostgreSQLConnection._instance = None


# Singleton accessor
_pg_connection: Optional[PostgreSQLConnection] = None


def get_pg_connection() -> PostgreSQLConnection:
    """Get PostgreSQL connection singleton."""
    global _pg_connection
    if _pg_connection is None:
        _pg_connection = PostgreSQLConnection()
    return _pg_connection
