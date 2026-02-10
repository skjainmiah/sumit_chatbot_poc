"""Database Explorer - browse all databases, tables, schemas, and data."""
import sqlite3
import os
import streamlit as st
import pandas as pd
from backend.config import settings


def get_databases():
    """Get visible databases from the registry."""
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        all_dbs = registry.get_all_databases()
        databases = {}
        for db_name, info in all_dbs.items():
            if db_name == "app":
                continue
            if not info.get("is_visible", True):
                continue
            databases[db_name] = {
                "path": info["db_path"],
                "display_name": info.get("display_name") or db_name.replace("_", " ").title(),
                "description": info.get("description", ""),
            }
        return databases
    except Exception:
        # Fallback to hardcoded if registry unavailable
        return {
            "crew_management": {
                "path": settings.crew_db_path,
                "display_name": "Crew Management",
                "description": "Crew members, qualifications, assignments, rest records, documents, contacts"
            },
            "flight_operations": {
                "path": settings.flight_db_path,
                "display_name": "Flight Operations",
                "description": "Airports, aircraft, flights, pairings, disruptions, hotels"
            },
            "hr_payroll": {
                "path": settings.hr_db_path,
                "display_name": "HR Payroll",
                "description": "Pay grades, payroll records, leave, benefits, performance reviews, expenses"
            },
            "compliance_training": {
                "path": settings.compliance_db_path,
                "display_name": "Compliance Training",
                "description": "Training courses/records, schedules, compliance checks, safety incidents, audit logs"
            },
        }


def get_table_list(db_path):
    """Get all tables and row counts from a database."""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in c.fetchall()]
        result = []
        for t in tables:
            try:
                c.execute(f"SELECT COUNT(*) FROM [{t}]")
                count = c.fetchone()[0]
                result.append({"table": t, "rows": count})
            except Exception:
                result.append({"table": t, "rows": 0})
        conn.close()
        return result
    except Exception as e:
        return []


def get_table_schema(db_path, table_name):
    """Get column info for a table."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(f"PRAGMA table_info([{table_name}])")
    columns = []
    for col in c.fetchall():
        columns.append({
            "Column": col[1],
            "Type": col[2],
            "Nullable": "YES" if not col[3] else "NO",
            "PK": "YES" if col[5] else "",
            "Default": col[4] or ""
        })
    conn.close()
    return columns


def get_table_data(db_path, table_name, limit=100):
    """Get data from a table."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM [{table_name}] LIMIT {limit}", conn)
    conn.close()
    return df


def get_create_statement(db_path, table_name):
    """Get DDL for a table."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""


def render_db_explorer():
    """Render the Database Explorer page."""
    st.title("🗄️ Database Explorer")
    st.caption("Browse all databases, tables, schemas, and data")

    # Get databases directly from config
    DATABASES = get_databases()

    # --- Overview Tab and Detail Tab ---
    tab_overview, tab_detail, tab_schema_meta, tab_col_desc = st.tabs(["📊 Overview", "🔍 Browse Tables", "📋 Schema Metadata", "🏷️ Column Descriptions"])

    # ===== OVERVIEW TAB =====
    with tab_overview:
        st.subheader("Available Databases")

        for db_name, info in DATABASES.items():
            display_name = info.get("display_name", db_name)

            with st.expander(f"📦 **{display_name}** - {info['description']}", expanded=False):
                if os.path.exists(info["path"]):
                    tables = get_table_list(info["path"])
                    if tables:
                        size_kb = os.path.getsize(info["path"]) / 1024
                        st.caption(f"Size: {size_kb:.0f} KB | Tables: {len(tables)}")
                        df = pd.DataFrame(tables)
                        st.dataframe(df, width="stretch", hide_index=True)
                    else:
                        st.info("No tables in this database")
                else:
                    st.error(f"Database file not found: {info['path']}")

        # Summary metrics
        st.divider()
        st.subheader("📈 Summary")
        total_tables = 0
        total_rows = 0
        db_count = 0

        for db_name, info in DATABASES.items():
            if os.path.exists(info["path"]):
                db_count += 1
                tables = get_table_list(info["path"])
                total_tables += len(tables)
                total_rows += sum(t["rows"] for t in tables)

        col1, col2, col3 = st.columns(3)
        col1.metric("Databases", db_count)
        col2.metric("Total Tables", total_tables)
        col3.metric("Total Rows", f"{total_rows:,}")

    # ===== BROWSE TABLES TAB =====
    with tab_detail:
        db_names = list(DATABASES.keys())

        if not db_names:
            st.info("No databases available. Upload a database first.")
        else:
            col1, col2 = st.columns([1, 2])

            with col1:
                selected_db = st.selectbox(
                    "Select Database",
                    db_names,
                    format_func=lambda x: DATABASES[x].get("display_name", x.replace("_", " ").title())
                )

            db_info = DATABASES[selected_db]
            if not os.path.exists(db_info["path"]):
                st.error(f"Database not found: {db_info['path']}")
                st.info("Upload a database to get started.")
            else:
                tables = get_table_list(db_info["path"])
                if not tables:
                    st.warning("No tables found in this database")
                else:
                    table_names = [t["table"] for t in tables]

                    with col2:
                        selected_table = st.selectbox("Select Table", table_names)

                    if selected_table:
                        # Schema
                        st.subheader(f"Schema: {selected_db}.{selected_table}")
                        schema = get_table_schema(db_info["path"], selected_table)
                        st.dataframe(pd.DataFrame(schema), width="stretch", hide_index=True)

                        # DDL
                        with st.expander("📄 CREATE TABLE Statement"):
                            ddl = get_create_statement(db_info["path"], selected_table)
                            st.code(ddl, language="sql")

                        # Data preview
                        st.subheader("📋 Data Preview")
                        row_limit = st.slider("Rows to show", 5, 200, 25, key="row_limit")
                        df = get_table_data(db_info["path"], selected_table, row_limit)
                        st.dataframe(df, width="stretch", hide_index=True)

                        row_count = next(t["rows"] for t in tables if t["table"] == selected_table)
                        st.caption(f"Showing {len(df)} of {row_count} total rows")

    # ===== SCHEMA METADATA TAB =====
    with tab_schema_meta:
        st.subheader("Schema Metadata (for LLM/Vector Search)")
        st.caption("This is the pre-indexed schema information used by the chatbot to find relevant tables.")

        if os.path.exists(settings.app_db_path):
            try:
                conn = sqlite3.connect(settings.app_db_path)
                c = conn.cursor()

                # Check if table exists
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_metadata'")
                if not c.fetchone():
                    st.warning("Schema metadata table not found. Run setup first:")
                    st.code("python scripts/run_all_setup.py", language="bash")
                    conn.close()
                    return

                c.execute("SELECT COUNT(*) FROM schema_metadata")
                count = c.fetchone()[0]

                if count > 0:
                    df = pd.read_sql_query(
                        "SELECT db_name, table_name, llm_description, row_count FROM schema_metadata ORDER BY db_name, table_name",
                        conn
                    )
                    st.dataframe(df, width="stretch", hide_index=True)
                    st.caption(f"{count} table schemas indexed")
                else:
                    st.warning("Schema metadata is empty. Run the setup to populate it:")
                    st.code("python scripts/run_all_setup.py", language="bash")
                conn.close()
            except Exception as e:
                st.error(f"Error reading schema metadata: {e}")
        else:
            st.error("App database not found. Run setup first:")
            st.code("python scripts/run_all_setup.py", language="bash")

    # ===== COLUMN DESCRIPTIONS TAB =====
    with tab_col_desc:
        st.subheader("Column Descriptions")
        st.caption("Review and edit LLM-generated column descriptions. These help the chatbot understand cryptic column names.")

        db_names_cd = list(DATABASES.keys())
        if not db_names_cd:
            st.warning("No databases available")
        else:
            selected_db_cd = st.selectbox(
                "Select Database",
                db_names_cd,
                format_func=lambda x: DATABASES[x].get("display_name", x.replace("_", " ").title()),
                key="cd_db_select"
            )

            # Load column descriptions from schema_metadata
            col_desc_data = _load_column_descriptions(selected_db_cd)

            if not col_desc_data:
                st.info("No schema metadata found for this database. Upload a database first or run setup.")
            else:
                table_names_cd = list(col_desc_data.keys())
                selected_table_cd = st.selectbox(
                    "Select Table",
                    table_names_cd,
                    key="cd_table_select"
                )

                if selected_table_cd and selected_table_cd in col_desc_data:
                    table_info = col_desc_data[selected_table_cd]
                    columns = table_info["columns"]
                    descriptions = table_info["descriptions"]

                    # Build editable dataframe
                    rows = []
                    for col in columns:
                        col_name = col["name"]
                        desc = descriptions.get(col_name, "")
                        is_unknown = desc.lower().startswith("unknown") if desc else True
                        rows.append({
                            "Column": col_name,
                            "Type": col["type"],
                            "Description": desc,
                        })

                    if rows:
                        df = pd.DataFrame(rows)

                        st.markdown("Edit descriptions below. Rows marked with **Unknown** need attention.")

                        edited_df = st.data_editor(
                            df,
                            column_config={
                                "Column": st.column_config.TextColumn("Column", disabled=True),
                                "Type": st.column_config.TextColumn("Type", disabled=True),
                                "Description": st.column_config.TextColumn("Description", width="large"),
                            },
                            hide_index=True,
                            use_container_width=True,
                            key=f"cd_editor_{selected_db_cd}_{selected_table_cd}"
                        )

                        # Highlight unknowns
                        unknown_count = sum(
                            1 for _, row in edited_df.iterrows()
                            if not row["Description"] or str(row["Description"]).lower().startswith("unknown")
                        )
                        if unknown_count > 0:
                            st.warning(f"{unknown_count} column(s) need descriptions")

                        if st.button("💾 Save Descriptions", key="cd_save_btn"):
                            _save_column_descriptions(selected_db_cd, selected_table_cd, edited_df)


def _load_column_descriptions(db_name: str) -> dict:
    """Load column descriptions from schema_metadata for a database."""
    import json
    try:
        conn = sqlite3.connect(settings.app_db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("""
            SELECT table_name, column_details, column_descriptions
            FROM schema_metadata
            WHERE db_name = ?
        """, (db_name,))

        result = {}
        for row in c.fetchall():
            table_name = row["table_name"]
            columns = []
            if row["column_details"]:
                for col_str in row["column_details"].split(", "):
                    parts = col_str.split(" (")
                    if len(parts) >= 2:
                        columns.append({
                            "name": parts[0].strip(),
                            "type": parts[1].rstrip(")")
                        })

            descriptions = {}
            if row["column_descriptions"]:
                try:
                    descriptions = json.loads(row["column_descriptions"])
                except (json.JSONDecodeError, TypeError):
                    pass

            result[table_name] = {
                "columns": columns,
                "descriptions": descriptions
            }

        conn.close()
        return result
    except Exception as e:
        st.error(f"Error loading column descriptions: {e}")
        return {}


def _save_column_descriptions(db_name: str, table_name: str, edited_df):
    """Save edited column descriptions back to schema_metadata."""
    import json
    try:
        # Build descriptions dict from edited dataframe
        descriptions = {}
        for _, row in edited_df.iterrows():
            if row["Description"]:
                descriptions[row["Column"]] = str(row["Description"])

        desc_json = json.dumps(descriptions)

        conn = sqlite3.connect(settings.app_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE schema_metadata
            SET column_descriptions = ?
            WHERE db_name = ? AND table_name = ?
        """, (desc_json, db_name, table_name))
        conn.commit()
        conn.close()

        # Refresh schema caches
        try:
            from backend.sql_upload.upload_service import refresh_all_schema
            refresh_all_schema()
        except Exception as e:
            st.warning(f"Descriptions saved but cache refresh failed: {e}")

        st.success(f"Descriptions saved for {db_name}.{table_name}. Schema refreshed!")
    except Exception as e:
        st.error(f"Failed to save descriptions: {e}")
