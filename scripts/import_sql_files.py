"""Import SQL files from data/sql_imports/ folder.

Drop .sql files in data/sql_imports/, run this script, and it will:
1. Detect SQL dialect for each file
2. Parse and create SQLite databases
3. Register databases in the registry
4. Populate schema metadata with LLM descriptions
5. Rebuild FAISS index
6. Reload V2 schema
7. Move processed files to data/sql_imports/processed/
"""
import sys
import os
import shutil
import glob
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings

# Directories
IMPORT_DIR = Path(settings.DATABASE_DIR).parent / "sql_imports"
PROCESSED_DIR = IMPORT_DIR / "processed"


def import_sql_files():
    """Scan and import all .sql files from the import directory."""
    print("=" * 60)
    print("  SQL File Importer")
    print("=" * 60)

    # Ensure directories exist
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Find .sql files
    sql_files = sorted(IMPORT_DIR.glob("*.sql"))

    if not sql_files:
        print(f"\nNo .sql files found in {IMPORT_DIR}")
        print("Place .sql files there and re-run this script.")
        return

    print(f"\nFound {len(sql_files)} SQL file(s) to process:\n")
    for f in sql_files:
        size_kb = f.stat().st_size / 1024
        print(f"  - {f.name} ({size_kb:.1f} KB)")

    # Import the upload service
    from backend.sql_upload.upload_service import UploadService
    service = UploadService()

    results = []
    for sql_file in sql_files:
        print(f"\n{'─' * 50}")
        print(f"Processing: {sql_file.name}")
        print(f"{'─' * 50}")

        try:
            # Read file
            content = sql_file.read_text(encoding="utf-8", errors="replace")

            # Validate
            is_valid, error = service.validate_file(content, sql_file.name)
            if not is_valid:
                print(f"  SKIPPED: {error}")
                results.append({"file": sql_file.name, "status": "skipped", "reason": error})
                continue

            # Process upload (user_id=0 for script imports)
            result = service.process_upload(
                file_content=content,
                filename=sql_file.name,
                user_id=0,
                auto_visible=True
            )

            if result.success:
                db_names = [d["db_name"] for d in result.databases_created]
                print(f"  SUCCESS: Created {len(result.databases_created)} database(s): {', '.join(db_names)}")
                print(f"  Tables: {result.total_tables}, Rows: {result.total_rows}")

                if result.warnings:
                    for w in result.warnings:
                        print(f"  WARNING: {w}")

                # Move to processed
                dest = PROCESSED_DIR / sql_file.name
                # Handle duplicate names
                counter = 1
                while dest.exists():
                    stem = sql_file.stem
                    dest = PROCESSED_DIR / f"{stem}_{counter}{sql_file.suffix}"
                    counter += 1
                shutil.move(str(sql_file), str(dest))
                print(f"  Moved to: {dest.name}")

                results.append({
                    "file": sql_file.name,
                    "status": "success",
                    "databases": db_names,
                    "tables": result.total_tables,
                    "rows": result.total_rows
                })
            else:
                errors = "; ".join(result.errors)
                print(f"  FAILED: {errors}")
                results.append({"file": sql_file.name, "status": "failed", "reason": errors})

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"file": sql_file.name, "status": "error", "reason": str(e)})

    # Rebuild FAISS + reload V2 schema for all new databases at once
    if any(r["status"] == "success" for r in results):
        print(f"\n{'─' * 50}")
        print("Post-processing: Rebuilding indexes...")
        print(f"{'─' * 50}")

        try:
            from backend.sql_upload.upload_service import refresh_schema_for_visible_databases
            refresh_schema_for_visible_databases()
            print("  FAISS index rebuilt and V2 schema reloaded.")
        except Exception as e:
            print(f"  WARNING: Post-processing failed: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print("  IMPORT SUMMARY")
    print(f"{'=' * 60}")
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] in ("failed", "error"))
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print(f"  Total files: {len(results)}")
    print(f"  Successful:  {success}")
    print(f"  Failed:      {failed}")
    print(f"  Skipped:     {skipped}")

    for r in results:
        icon = "✓" if r["status"] == "success" else "✗" if r["status"] in ("failed", "error") else "−"
        detail = ""
        if r["status"] == "success":
            detail = f" → {', '.join(r['databases'])} ({r['tables']} tables, {r['rows']} rows)"
        elif "reason" in r:
            detail = f" → {r['reason']}"
        print(f"  {icon} {r['file']}{detail}")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    import_sql_files()
