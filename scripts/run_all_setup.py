"""Master setup script - runs all setup tasks in order."""
import sys
import os
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(text):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def run_step(description, func):
    """Run a setup step with error handling."""
    print(f"Starting: {description}...")
    try:
        func()
        print(f"Completed: {description}\n")
        return True
    except Exception as e:
        print(f"ERROR in {description}: {e}\n")
        return False


def setup_databases():
    """Set up all SQLite databases with seed data."""
    from backend.db.setup_databases import setup_all
    setup_all()


def seed_users():
    """Seed admin and test users."""
    from scripts.seed_admin_user import seed_admin_user, seed_test_user
    seed_admin_user()
    seed_test_user()


def populate_schema_metadata():
    """Populate schema metadata with hand-written descriptions (no LLM)."""
    from scripts.populate_schema_metadata import populate
    populate()


def build_faiss_indexes():
    """Build FAISS vector indexes for schema and document search."""
    from scripts.build_faiss_index import build_schema_index, build_document_index
    build_schema_index()


def process_sql_imports():
    """Process any SQL files in data/sql_imports/ folder."""
    from pathlib import Path
    from backend.config import settings as _settings
    import_dir = Path(_settings.DATABASE_DIR).parent / "sql_imports"
    sql_files = list(import_dir.glob("*.sql")) if import_dir.exists() else []
    if sql_files:
        from scripts.import_sql_files import import_sql_files
        import_sql_files()
    else:
        print("  No .sql files found in data/sql_imports/ - skipping.")


def verify_setup():
    """Verify the setup was successful."""
    from backend.config import settings

    print("Verifying setup...")

    # Check databases exist
    databases = [
        ("App DB", settings.app_db_path),
        ("Crew DB", settings.crew_db_path),
        ("Flights DB", settings.flight_db_path),
        ("HR DB", settings.hr_db_path),
        ("Compliance DB", settings.compliance_db_path),
    ]

    all_ok = True
    for name, path in databases:
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024
            print(f"  [OK] {name}: {path} ({size:.1f} KB)")
        else:
            print(f"  [MISSING] {name}: {path}")
            all_ok = False

    # Check FAISS indexes
    faiss_dir = settings.FAISS_INDEX_DIR
    faiss_files = [
        ("Schema Index", os.path.join(faiss_dir, "schema_metadata.index")),
        ("Document Index", os.path.join(faiss_dir, "document_chunks.index")),
    ]

    for name, path in faiss_files:
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024
            print(f"  [OK] {name}: {path} ({size:.1f} KB)")
        else:
            print(f"  [MISSING] {name}: {path}")

    return all_ok


def main():
    """Run all setup steps."""
    print_header("AIRLINE CREW CHATBOT - SETUP")

    print("This script will:")
    print("  1. Create SQLite databases with seed data")
    print("  2. Create admin and test users")
    print("  3. Populate schema metadata (no API key needed)")
    print("  4. Build FAISS indexes (requires LLM API)")
    print("  5. Process SQL imports from data/sql_imports/")
    print("\nNote: Step 4 requires LLM_CHAT_URL and LLM_API_KEY in .env")

    # Check for API key
    from backend.config import settings
    if not settings.LLM_API_KEY:
        print("\n[WARNING] LLM_API_KEY not found in environment.")
        print("  Step 4 will be skipped.")
        print("  Set LLM_CHAT_URL and LLM_API_KEY in .env file and re-run.")

    print_header("Step 1: Setting up databases")
    run_step("Database setup", setup_databases)

    print_header("Step 2: Seeding users")
    run_step("User seeding", seed_users)

    print_header("Step 3: Populating schema metadata")
    run_step("Schema metadata population", populate_schema_metadata)

    if settings.LLM_API_KEY:
        print_header("Step 4: Building FAISS indexes")
        run_step("FAISS index building", build_faiss_indexes)
    else:
        print_header("Skipping Step 4 (No API key)")
        print("Set LLM_CHAT_URL and LLM_API_KEY in .env and run:")
        print("  python scripts/build_faiss_index.py")

    print_header("Step 5: Processing SQL imports")
    run_step("SQL file imports", process_sql_imports)

    print_header("Verification")
    verify_setup()

    print_header("SETUP COMPLETE")
    print("To start the application:")
    print("  1. Backend:  uvicorn backend.main:app --reload")
    print("  2. Frontend: streamlit run frontend/app.py")
    print("\nDefault credentials:")
    print("  Admin: admin / admin123")
    print("  User:  testuser / test123")


if __name__ == "__main__":
    main()
