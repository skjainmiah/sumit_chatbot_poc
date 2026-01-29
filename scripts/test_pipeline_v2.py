"""
Test script for the new PostgreSQL pipeline.

Usage:
    python scripts/test_pipeline_v2.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_schema_loader():
    """Test schema loading."""
    print("\n" + "=" * 50)
    print("Testing Schema Loader")
    print("=" * 50)

    try:
        from backend.schema.loader import get_schema_loader

        loader = get_schema_loader()
        stats = loader.get_stats()

        print(f"Databases: {stats.total_databases}")
        print(f"Tables: {stats.total_tables}")
        print(f"Columns: {stats.total_columns}")
        print(f"Estimated tokens: {stats.estimated_tokens:,}")

        print("\nDatabase names:")
        for db in loader.get_database_names():
            print(f"  - {db}")

        print("\n Schema loaded successfully")
        return True

    except FileNotFoundError as e:
        print(f" Schema file not found: {e}")
        print("\nRun the schema extractor first:")
        print("  python scripts/extract_pg_schema.py --all")
        return False

    except Exception as e:
        print(f" Error: {e}")
        return False


def test_database_connection():
    """Test PostgreSQL connection."""
    print("\n" + "=" * 50)
    print("Testing PostgreSQL Connection")
    print("=" * 50)

    try:
        from backend.db.postgres import get_pg_connection

        pg = get_pg_connection()
        if pg.test_connection():
            print(" Connected successfully")

            # Test a simple query
            result = pg.execute_query("SELECT version()")
            print(f"PostgreSQL version: {result['rows'][0]['version'][:50]}...")
            return True
        else:
            print(" Connection test failed")
            return False

    except Exception as e:
        print(f" Error: {e}")
        print("\nCheck your .env file has correct PostgreSQL credentials:")
        print("  PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE")
        return False


def test_pipeline():
    """Test the SQL pipeline with sample queries."""
    print("\n" + "=" * 50)
    print("Testing SQL Pipeline")
    print("=" * 50)

    try:
        from backend.sql.pipeline_v2 import get_sql_pipeline

        pipeline = get_sql_pipeline()

        # Test queries
        test_queries = [
            # Meta queries
            ("List available databases", "meta"),
            ("How many tables are there?", "meta"),
            ("Show all tables", "meta"),

            # Data queries (these will fail without actual data, but should generate SQL)
            # ("Show all employees", "data"),
            # ("Count records in users table", "data"),
        ]

        for query, expected_intent in test_queries:
            print(f"\nQuery: '{query}'")
            result = pipeline.run(query)

            intent = result.get("intent", "unknown")
            print(f"  Intent: {intent} (expected: {expected_intent})")
            print(f"  Success: {result.get('success', False)}")
            print(f"  Time: {result.get('processing_time_ms', 0)}ms")

            if intent == "meta":
                answer = result.get("answer", "")
                print(f"  Answer: {answer[:100]}..." if len(answer) > 100 else f"  Answer: {answer}")

            elif intent == "data" and result.get("sql"):
                print(f"  SQL: {result['sql'][:100]}...")

            if not result.get("success") and result.get("error"):
                print(f"  Error: {result['error']}")

        print("\n Pipeline tests completed")
        return True

    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("PostgreSQL Pipeline V2 - Test Suite")
    print("=" * 60)

    # Check environment
    required_vars = ["PGHOST", "PGUSER", "PGPASSWORD"]
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        print(f"\n Warning: Missing environment variables: {missing}")
        print("Set them in .env or export them before running tests.")

    results = {}

    # Run tests
    results["schema"] = test_schema_loader()

    if results["schema"]:
        results["database"] = test_database_connection()

        if results["database"]:
            results["pipeline"] = test_pipeline()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "" if passed else ""
        print(f"  {status} {test_name}")

    all_passed = all(results.values())
    print(f"\n{'All tests passed!' if all_passed else 'Some tests failed.'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
