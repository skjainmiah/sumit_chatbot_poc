"""Upload service - orchestrates the full SQL upload flow."""
import os
import re
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

import logging
import pandas as pd

from backend.config import settings
from backend.sql_upload.pg_parser import PgDumpParser
from backend.sql_upload.mssql_parser import MssqlDumpParser
from backend.sql_upload.dialect_detector import SqlDialect, detect_sql_dialect
from backend.sql_upload.db_creator import DatabaseCreator, CreationResult
from backend.db.registry import get_database_registry
from backend.llm.prompts import SCHEMA_DESCRIPTION_PROMPT

logger = logging.getLogger("chatbot.upload_service")


@dataclass
class UploadResult:
    """Result of SQL file upload processing."""
    success: bool
    upload_id: Optional[int] = None
    dialect: str = "unknown"
    databases_created: List[Dict] = field(default_factory=list)
    total_tables: int = 0
    total_rows: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class UploadService:
    """Orchestrates SQL file upload, parsing, and database creation."""

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self):
        self.registry = get_database_registry()

    def process_upload(
        self,
        file_content: str,
        filename: str,
        user_id: int,
        auto_visible: bool = True
    ) -> UploadResult:
        """Process an uploaded SQL file.

        Args:
            file_content: The SQL file content
            filename: Original filename
            user_id: ID of uploading user
            auto_visible: Whether to make created databases visible

        Returns:
            UploadResult with details of created databases
        """
        errors = []
        warnings = []
        databases_created = []
        total_tables = 0
        total_rows = 0

        # Create upload history record
        upload_id = self._create_upload_record(user_id, filename)

        try:
            # Auto-detect SQL dialect
            dialect, confidence = detect_sql_dialect(file_content)
            dialect_str = dialect.value

            if dialect == SqlDialect.UNKNOWN:
                # Default to PostgreSQL if unknown
                dialect = SqlDialect.POSTGRESQL
                dialect_str = "postgresql"
                warnings.append(f"Could not determine SQL dialect (confidence: {confidence:.0%}). Assuming PostgreSQL.")
            else:
                if confidence < 0.7:
                    warnings.append(f"SQL dialect detected as {dialect_str} with {confidence:.0%} confidence.")

            # Select appropriate parser
            if dialect == SqlDialect.MSSQL:
                parser = MssqlDumpParser()
                creator = DatabaseCreator(dialect="mssql")
            else:
                parser = PgDumpParser()
                creator = DatabaseCreator(dialect="postgresql")

            # Parse SQL content
            parsed_databases = parser.parse(file_content)

            if not parsed_databases:
                errors.append("No valid database structures found in SQL file")
                self._update_upload_record(upload_id, "failed", error_message=errors[0])
                return UploadResult(
                    success=False,
                    upload_id=upload_id,
                    dialect=dialect_str,
                    errors=errors,
                    warnings=warnings
                )

            # Create each database
            for parsed_db in parsed_databases:
                result = creator.create_database(parsed_db)

                if result.success:
                    # Register in database registry
                    try:
                        # Read actual table names from the created DB for description
                        table_names = []
                        try:
                            tmp_conn = sqlite3.connect(result.db_path)
                            tmp_cur = tmp_conn.cursor()
                            tmp_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                            table_names = [r[0] for r in tmp_cur.fetchall()]
                            tmp_conn.close()
                        except Exception:
                            pass

                        db_description = self._generate_db_description(result.db_name, table_names) if table_names else (
                            f"Database with {result.tables_created} tables"
                        )

                        db_id = self.registry.register_database(
                            db_name=result.db_name,
                            db_path=result.db_path,
                            display_name=result.db_name.replace("_", " ").title(),
                            description=db_description,
                            source_type="uploaded",
                            is_visible=auto_visible,
                            upload_filename=filename,
                            uploaded_by=user_id,
                            table_count=result.tables_created
                        )

                        databases_created.append({
                            "db_id": db_id,
                            "db_name": result.db_name,
                            "db_path": result.db_path,
                            "tables_created": result.tables_created,
                            "rows_inserted": result.rows_inserted
                        })

                        total_tables += result.tables_created
                        total_rows += result.rows_inserted

                        if result.errors:
                            warnings.extend(result.errors)

                    except Exception as e:
                        errors.append(f"Failed to register {result.db_name}: {str(e)}")
                        # Clean up created database
                        if os.path.exists(result.db_path):
                            try:
                                os.remove(result.db_path)
                            except OSError:
                                pass
                else:
                    errors.extend(result.errors)

            # Update upload history
            if databases_created:
                db_names = json.dumps([d["db_name"] for d in databases_created])
                self._update_upload_record(
                    upload_id,
                    "completed",
                    databases_created=db_names,
                    tables_created=total_tables
                )

                # Run full schema setup for new databases
                self._run_schema_setup(databases_created)

            else:
                self._update_upload_record(
                    upload_id,
                    "failed",
                    error_message="; ".join(errors) if errors else "No databases created"
                )

            return UploadResult(
                success=len(databases_created) > 0,
                upload_id=upload_id,
                dialect=dialect_str,
                databases_created=databases_created,
                total_tables=total_tables,
                total_rows=total_rows,
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            error_msg = f"Upload processing failed: {str(e)}"
            errors.append(error_msg)
            self._update_upload_record(upload_id, "failed", error_message=error_msg)

            return UploadResult(
                success=False,
                upload_id=upload_id,
                errors=errors,
                warnings=warnings
            )

    def process_csv_upload(
        self,
        files: List[Tuple[str, bytes]],
        db_name: str,
        user_id: int,
        is_new_db: bool = True,
        auto_visible: bool = True
    ) -> UploadResult:
        """Process uploaded CSV/Excel files into a SQLite database.

        Args:
            files: List of (filename, file_bytes) tuples
            db_name: Target database name
            user_id: ID of uploading user
            is_new_db: Whether to create a new database or add to existing
            auto_visible: Whether to make the database visible after upload

        Returns:
            UploadResult with details of created tables
        """
        errors = []
        warnings = []
        tables_created_list = []
        total_tables = 0
        total_rows = 0

        # Sanitize db_name
        db_name_clean = re.sub(r'[^a-z0-9_]', '_', db_name.lower().strip())
        db_name_clean = re.sub(r'_+', '_', db_name_clean).strip('_')
        if not db_name_clean:
            return UploadResult(success=False, errors=["Invalid database name"])

        db_path = os.path.join(settings.DATABASE_DIR, f"{db_name_clean}.db")
        Path(settings.DATABASE_DIR).mkdir(parents=True, exist_ok=True)

        # Validate target
        if is_new_db and os.path.exists(db_path):
            return UploadResult(
                success=False,
                errors=[f"Database '{db_name_clean}' already exists. Use 'Add to existing' instead."]
            )
        if not is_new_db and not os.path.exists(db_path):
            return UploadResult(
                success=False,
                errors=[f"Database '{db_name_clean}' not found. Use 'Create new' instead."]
            )

        # Create upload history record
        combined_filenames = ", ".join(f[0] for f in files)
        upload_id = self._create_upload_record(user_id, combined_filenames)

        try:
            conn = sqlite3.connect(db_path)

            for filename, file_bytes in files:
                try:
                    import io
                    ext = os.path.splitext(filename)[1].lower()

                    # Build list of (table_name, dataframe) pairs
                    sheets_to_load = []

                    if ext == '.csv':
                        df = pd.read_csv(io.BytesIO(file_bytes))
                        base_name = os.path.splitext(filename)[0]
                        table_name = re.sub(r'[^a-z0-9_]', '_', base_name.lower().strip())
                        table_name = re.sub(r'_+', '_', table_name).strip('_') or f"table_{total_tables + 1}"
                        sheets_to_load.append((table_name, df))

                    elif ext in ('.xlsx', '.xls'):
                        # Read ALL sheets — each sheet becomes a separate table
                        all_sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
                        for sheet_name, df in all_sheets.items():
                            table_name = re.sub(r'[^a-z0-9_]', '_', sheet_name.lower().strip())
                            table_name = re.sub(r'_+', '_', table_name).strip('_') or f"table_{total_tables + 1}"
                            sheets_to_load.append((table_name, df))
                    else:
                        warnings.append(f"Skipped '{filename}': unsupported format ({ext})")
                        continue

                    # Write each sheet/dataframe to SQLite
                    for table_name, df in sheets_to_load:
                        row_count = len(df)
                        df.to_sql(table_name, conn, if_exists='replace', index=False)

                        tables_created_list.append({
                            "table_name": table_name,
                            "row_count": row_count,
                            "columns": len(df.columns)
                        })
                        total_tables += 1
                        total_rows += row_count

                except Exception as e:
                    errors.append(f"Failed to process '{filename}': {str(e)}")

            conn.close()

            if total_tables == 0:
                self._update_upload_record(upload_id, "failed", error_message="No tables created")
                return UploadResult(
                    success=False,
                    upload_id=upload_id,
                    dialect="csv",
                    errors=errors if errors else ["No valid files to process"],
                    warnings=warnings
                )

            # Register or update in database registry
            db_info = {
                "db_name": db_name_clean,
                "db_path": db_path,
                "tables_created": total_tables,
                "rows_inserted": total_rows
            }

            if is_new_db:
                # Generate a meaningful description from table names
                created_table_names = [t["table_name"] for t in tables_created_list]
                db_description = self._generate_db_description(db_name_clean, created_table_names)

                self.registry.register_database(
                    db_name=db_name_clean,
                    db_path=db_path,
                    display_name=db_name_clean.replace("_", " ").title(),
                    description=db_description,
                    source_type="uploaded",
                    is_visible=auto_visible,
                    upload_filename=combined_filenames,
                    uploaded_by=user_id,
                    table_count=total_tables
                )
            else:
                # Update table count for existing DB
                existing_info = self.registry.get_database_info(db_name_clean)
                old_count = existing_info.get("table_count", 0) if existing_info else 0
                self.registry.update_database(db_name_clean, table_count=old_count + total_tables)

            # Update upload history
            self._update_upload_record(
                upload_id,
                "completed",
                databases_created=json.dumps([db_name_clean]),
                tables_created=total_tables
            )

            # Run schema setup
            self._run_schema_setup([db_info])

            return UploadResult(
                success=True,
                upload_id=upload_id,
                dialect="csv",
                databases_created=[db_info],
                total_tables=total_tables,
                total_rows=total_rows,
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            error_msg = f"CSV upload failed: {str(e)}"
            errors.append(error_msg)
            self._update_upload_record(upload_id, "failed", error_message=error_msg)
            return UploadResult(
                success=False,
                upload_id=upload_id,
                errors=errors,
                warnings=warnings
            )

    def _create_upload_record(self, user_id: int, filename: str) -> int:
        """Create upload history record."""
        conn = sqlite3.connect(settings.app_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO upload_history (user_id, filename, status) VALUES (?, ?, 'processing')",
            (user_id, filename)
        )
        upload_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return upload_id

    def _update_upload_record(
        self,
        upload_id: int,
        status: str,
        databases_created: str = None,
        tables_created: int = None,
        error_message: str = None
    ) -> None:
        """Update upload history record."""
        conn = sqlite3.connect(settings.app_db_path)
        cursor = conn.cursor()

        updates = ["status = ?"]
        values = [status]

        if databases_created is not None:
            updates.append("databases_created = ?")
            values.append(databases_created)

        if tables_created is not None:
            updates.append("tables_created = ?")
            values.append(tables_created)

        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message[:500] if error_message else None)

        values.append(upload_id)
        sql = f"UPDATE upload_history SET {', '.join(updates)} WHERE upload_id = ?"

        cursor.execute(sql, values)
        conn.commit()
        conn.close()

    def _run_schema_setup(self, databases: List[Dict]) -> None:
        """Run full schema setup: populate metadata, rebuild FAISS index, reload V2 schema."""
        # Step 1: Populate schema metadata for new databases
        self._populate_schema_for_databases(databases)

        # Step 2: Detect FK relationships from matching column names
        self._detect_foreign_keys(databases)

        # Step 3: Rebuild FAISS index (for V1 old chat)
        self._rebuild_faiss_index()

        # Step 4: Reload V2 schema (for V2 new chat)
        self._reload_v2_schema()

    def _detect_foreign_keys(self, databases: List[Dict]) -> None:
        """Detect likely FK relationships by scanning matching column names across tables.

        For each database, builds a map of column_name → list of tables that have it.
        Columns ending in '_id' (or named 'id') that appear in multiple tables are
        treated as foreign key links. The table with fewer rows is assumed to reference
        the table with more rows (detail → master).

        Results are stored as JSON in schema_metadata.detected_foreign_keys.
        """
        app_conn = sqlite3.connect(settings.app_db_path)
        app_cursor = app_conn.cursor()

        # Ensure column exists (for databases created before migration)
        try:
            app_cursor.execute("ALTER TABLE schema_metadata ADD COLUMN detected_foreign_keys TEXT")
            app_conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

        for db_info in databases:
            db_name = db_info["db_name"]
            db_path = db_info["db_path"]

            try:
                db_conn = sqlite3.connect(db_path)
                db_conn.row_factory = sqlite3.Row
                db_cursor = db_conn.cursor()

                # Get all tables
                db_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                tables = [row["name"] for row in db_cursor.fetchall()]

                if len(tables) < 2:
                    db_conn.close()
                    continue

                # Build column → tables map and table → row_count map
                col_to_tables: Dict[str, List[str]] = {}
                table_row_counts: Dict[str, int] = {}

                for table_name in tables:
                    db_cursor.execute(f"PRAGMA table_info([{table_name}])")
                    for col in db_cursor.fetchall():
                        col_name = col["name"]
                        if col_name not in col_to_tables:
                            col_to_tables[col_name] = []
                        col_to_tables[col_name].append(table_name)

                    db_cursor.execute(f"SELECT COUNT(*) as cnt FROM [{table_name}]")
                    table_row_counts[table_name] = db_cursor.fetchone()["cnt"]

                db_conn.close()

                # Find shared columns that look like join keys
                # Heuristic: column appears in 2+ tables AND (ends with _id OR is named 'id')
                shared_keys = {}
                for col_name, owning_tables in col_to_tables.items():
                    if len(owning_tables) < 2:
                        continue
                    is_id_col = col_name.lower().endswith("_id") or col_name.lower() == "id"
                    if not is_id_col:
                        continue
                    shared_keys[col_name] = owning_tables

                # Build FK relationships per table
                # For each shared key, the table with more rows references the one with fewer
                # (detail table → master/lookup table)
                table_fks: Dict[str, List[Dict]] = {t: [] for t in tables}

                for col_name, owning_tables in shared_keys.items():
                    # Sort by row count ascending (smallest = likely master)
                    sorted_tables = sorted(owning_tables, key=lambda t: table_row_counts.get(t, 0))
                    master_table = sorted_tables[0]

                    for detail_table in sorted_tables[1:]:
                        table_fks[detail_table].append({
                            "from_column": col_name,
                            "to_table": master_table,
                            "to_column": col_name
                        })

                # Write FK data into schema_metadata
                for table_name, fks in table_fks.items():
                    if not fks:
                        continue
                    fk_json = json.dumps(fks)
                    app_cursor.execute("""
                        UPDATE schema_metadata
                        SET detected_foreign_keys = ?
                        WHERE db_name = ? AND table_name = ?
                    """, (fk_json, db_name, table_name))

                logger.info(f"Detected FK relationships for {db_name}: "
                           f"{sum(len(v) for v in table_fks.values())} links across {len(tables)} tables")

            except Exception as e:
                logger.warning(f"FK detection failed for {db_name}: {e}")

        app_conn.commit()
        app_conn.close()

    def _generate_db_description(self, db_name: str, table_names: List[str]) -> str:
        """Generate a meaningful database-level description from table names.

        Builds a concise summary listing the tables and uses LLM if available
        to produce a richer description. Falls back to table-name-based text.
        """
        # Build a readable table list
        table_list = ", ".join(table_names[:10])
        if len(table_names) > 10:
            table_list += f" and {len(table_names) - 10} more"

        # Try LLM for a richer description
        try:
            from backend.llm.client import get_llm_client
            client = get_llm_client()

            prompt = (
                f"Write a 1-sentence description of a database named '{db_name}' "
                f"that contains {len(table_names)} tables: {table_list}.\n"
                f"Focus on what domain/business area this database covers based on the table names. "
                f"Do not mention 'uploaded' or file formats. Just describe the data content."
            )
            desc = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150,
                use_fast_model=True,
            )
            if desc and desc.strip():
                return desc.strip()
        except Exception as e:
            logger.warning(f"LLM DB description failed for {db_name}: {e}")

        # Fallback: table-name-based description
        return f"Database with {len(table_names)} tables: {table_list}"

    def _generate_llm_description(self, db_name: str, table_name: str,
                                   col_details: str, sample_str: str) -> Optional[str]:
        """Generate a rich table description using LLM."""
        try:
            from backend.llm.client import get_llm_client
            client = get_llm_client()

            prompt = SCHEMA_DESCRIPTION_PROMPT.format(
                db_name=db_name,
                table_name=table_name,
                columns=col_details,
                sample_data=sample_str
            )

            description = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
                use_fast_model=True
            )
            return description.strip() if description else None
        except Exception as e:
            logger.warning(f"LLM description generation failed for {db_name}.{table_name}: {e}")
            return None

    def _populate_schema_for_databases(self, databases: List[Dict]) -> None:
        """Populate schema metadata for specified databases with LLM descriptions."""
        conn = sqlite3.connect(settings.app_db_path)
        cursor = conn.cursor()

        for db_info in databases:
            db_name = db_info["db_name"]
            db_path = db_info["db_path"]

            try:
                db_conn = sqlite3.connect(db_path)
                db_conn.row_factory = sqlite3.Row
                db_cursor = db_conn.cursor()

                # Get all tables
                db_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                tables = [row["name"] for row in db_cursor.fetchall()]

                for table_name in tables:
                    # Get columns
                    db_cursor.execute(f"PRAGMA table_info([{table_name}])")
                    columns = []
                    for col in db_cursor.fetchall():
                        columns.append(f"{col['name']} ({col['type']})")
                    col_details = ", ".join(columns)

                    # Get row count
                    db_cursor.execute(f"SELECT COUNT(*) as cnt FROM [{table_name}]")
                    row_count = db_cursor.fetchone()["cnt"]

                    # Get DDL
                    db_cursor.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,)
                    )
                    ddl = db_cursor.fetchone()["sql"] or ""

                    # Get sample values
                    db_cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 3")
                    sample = [dict(r) for r in db_cursor.fetchall()]
                    sample_str = json.dumps(sample, default=str)[:500]

                    # Try LLM-generated description first
                    desc = self._generate_llm_description(
                        db_name, table_name, col_details, sample_str
                    )

                    # Fallback to improved template if LLM fails
                    if not desc:
                        # Heuristic based on column names
                        col_names_lower = col_details.lower()
                        heuristic = "general data"
                        if "employee" in col_names_lower or "name" in col_names_lower:
                            heuristic = "personnel or employee records"
                        elif "amount" in col_names_lower or "price" in col_names_lower or "pay" in col_names_lower:
                            heuristic = "financial or payment data"
                        elif "date" in col_names_lower and "flight" in col_names_lower:
                            heuristic = "flight schedule or operations data"
                        elif "score" in col_names_lower or "training" in col_names_lower:
                            heuristic = "training or assessment records"

                        desc = (f"Table {table_name} in {db_name} database. "
                                f"Contains {row_count} rows. "
                                f"Columns: {col_details[:200]}. "
                                f"Sample values suggest this table stores {heuristic}.")

                    # Insert into schema_metadata
                    cursor.execute("""
                        INSERT OR REPLACE INTO schema_metadata
                        (db_name, table_name, column_details, row_count, sample_values, ddl_statement, llm_description)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (db_name, table_name, col_details, row_count, sample_str, ddl, desc))

                db_conn.close()

            except Exception as e:
                logger.warning(f"Failed to populate schema for {db_name}: {e}")

        conn.commit()
        conn.close()

    def _rebuild_faiss_index(self) -> None:
        """Rebuild FAISS index from schema_metadata."""
        try:
            from backend.cache.vector_store import get_schema_store
            from backend.llm.embeddings import embed_documents

            store = get_schema_store()

            # Clear existing index
            store.clear()

            # Load all schema metadata
            conn = sqlite3.connect(settings.app_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Load all databases from schema_metadata
            cursor.execute("""
                SELECT db_name, table_name, column_details, row_count,
                       sample_values, ddl_statement, llm_description
                FROM schema_metadata
            """)

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                print("No schema metadata to index")
                return

            # Prepare texts and metadata for indexing
            texts = []
            metadata_list = []

            for row in rows:
                # Create searchable text
                text = f"{row['db_name']} {row['table_name']} {row['llm_description']}"
                texts.append(text)

                # Parse columns from column_details
                columns = []
                if row['column_details']:
                    for col_str in row['column_details'].split(", "):
                        parts = col_str.split(" (")
                        if len(parts) >= 2:
                            columns.append({
                                "name": parts[0],
                                "type": parts[1].rstrip(")")
                            })

                metadata_list.append({
                    "db_name": row['db_name'],
                    "table_name": row['table_name'],
                    "description": row['llm_description'],
                    "columns": columns,
                    "ddl": row['ddl_statement'],
                    "row_count": row['row_count']
                })

            # Add to FAISS index
            store.add(texts, metadata_list)
            print(f"FAISS index rebuilt with {len(texts)} tables")

        except Exception as e:
            print(f"Warning: Failed to rebuild FAISS index: {e}")

    def _reload_v2_schema(self) -> None:
        """Reload V2 schema loader and pipeline to include uploaded databases."""
        try:
            from backend.schema.loader import reload_schema
            reload_schema()

            # Refresh V2 pipeline's cached system prompt (without reloading again)
            from backend.sql.pipeline_v2 import _pipeline
            if _pipeline is not None:
                _pipeline.refresh_schema(reload_loader=False)

            print("V2 schema reloaded with uploaded databases")
        except Exception as e:
            print(f"Warning: Failed to reload V2 schema: {e}")

    def get_upload_history(self, user_id: int = None, limit: int = 50) -> List[Dict]:
        """Get upload history, optionally filtered by user."""
        conn = sqlite3.connect(settings.app_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if user_id:
            cursor.execute(
                "SELECT * FROM upload_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM upload_history ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def validate_file(self, file_content: str, filename: str) -> tuple[bool, str]:
        """Validate uploaded file before processing.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file extension
        if not filename.lower().endswith(".sql"):
            return False, "File must have .sql extension"

        # Check file size
        content_size = len(file_content.encode("utf-8"))
        if content_size > self.MAX_FILE_SIZE:
            return False, f"File too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)}MB"

        # Check for minimum content
        if len(file_content.strip()) < 50:
            return False, "File appears to be empty or too small"

        # Check for SQL-like content
        sql_keywords = ["CREATE", "INSERT", "TABLE", "SELECT"]
        content_upper = file_content.upper()
        if not any(kw in content_upper for kw in sql_keywords):
            return False, "File does not appear to contain valid SQL"

        return True, ""


def refresh_all_schema() -> None:
    """Refresh schema metadata, FAISS index, V2 schema, and V1 keyword cache.

    Call this when databases are added or updated.
    """
    # Clear V1 keyword cache so it reloads
    from backend.sql.schema_cache import reload_cache
    reload_cache()

    service = UploadService()
    service._rebuild_faiss_index()
    service._reload_v2_schema()


def remove_schema_for_database(db_name: str) -> None:
    """Remove schema metadata for a specific database."""
    conn = sqlite3.connect(settings.app_db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schema_metadata WHERE db_name = ?", (db_name,))
    conn.commit()
    conn.close()

    # Rebuild FAISS index and reload V2 schema
    refresh_all_schema()
