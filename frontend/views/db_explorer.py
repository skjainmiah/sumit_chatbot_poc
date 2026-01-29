"""Database Explorer - browse all databases, tables, schemas, and data."""
import sqlite3
import os
import streamlit as st
import pandas as pd
from backend.config import settings


def get_databases_from_registry():
    """Get databases from registry, with fallback to static config."""
    try:
        from backend.db.registry import get_database_registry
        registry = get_database_registry()
        all_dbs = registry.get_all_databases()

        if all_dbs:
            databases = {}
            for db_name, info in all_dbs.items():
                if db_name == "app":
                    continue  # Skip app database
                databases[db_name] = {
                    "path": info["db_path"],
                    "description": info.get("description", ""),
                    "source_type": info.get("source_type", "unknown"),
                    "is_visible": info.get("is_visible", True),
                    "display_name": info.get("display_name", db_name)
                }
            if databases:
                return databases
    except Exception as e:
        st.warning(f"Registry error: {e}")

    # Fallback to static config
    return get_static_databases()


def get_static_databases():
    """Get static database configuration."""
    databases = {}

    # Check each database file exists
    db_configs = [
        ("crew_management", settings.crew_db_path, "Crew Management",
         "Crew members, qualifications, assignments, rest records, documents, contacts"),
        ("flight_operations", settings.flight_db_path, "Flight Operations",
         "Airports, aircraft, flights, pairings, disruptions, hotels"),
        ("hr_payroll", settings.hr_db_path, "HR Payroll",
         "Pay grades, payroll records, leave, benefits, performance reviews, expenses"),
        ("compliance_training", settings.compliance_db_path, "Compliance Training",
         "Training courses/records, schedules, compliance checks, safety incidents, audit logs"),
    ]

    for db_name, db_path, display_name, description in db_configs:
        if os.path.exists(db_path):
            databases[db_name] = {
                "path": db_path,
                "description": description,
                "source_type": "mock",
                "is_visible": True,
                "display_name": display_name
            }

    return databases


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

    # Get databases
    DATABASES = get_databases_from_registry()

    if not DATABASES:
        st.error("No databases found!")
        st.info("Run the setup script to create mock databases:")
        st.code("python scripts/run_all_setup.py", language="bash")
        return

    # --- Overview Tab and Detail Tab ---
    tab_overview, tab_detail, tab_schema_meta = st.tabs(["📊 Overview", "🔍 Browse Tables", "📋 Schema Metadata"])

    # ===== OVERVIEW TAB =====
    with tab_overview:
        st.subheader("Available Databases")

        for db_name, info in DATABASES.items():
            # Show visibility status
            visibility_icon = "👁️" if info.get("is_visible", True) else "🚫"
            source_badge = "📦" if info.get("source_type") == "mock" else "⬆️" if info.get("source_type") == "uploaded" else ""
            display_name = info.get("display_name", db_name)

            with st.expander(f"{visibility_icon} **{display_name}** {source_badge} - {info['description']}", expanded=False):
                if os.path.exists(info["path"]):
                    tables = get_table_list(info["path"])
                    if tables:
                        size_kb = os.path.getsize(info["path"]) / 1024
                        st.caption(f"Size: {size_kb:.0f} KB | Tables: {len(tables)}")
                        df = pd.DataFrame(tables)
                        st.dataframe(df, use_container_width=True, hide_index=True)
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
        if not DATABASES:
            st.warning("No databases available")
            return

        col1, col2 = st.columns([1, 2])

        db_names = list(DATABASES.keys())

        with col1:
            selected_db = st.selectbox(
                "Select Database",
                db_names,
                format_func=lambda x: DATABASES[x].get("display_name", x.replace("_", " ").title())
            )

        if not selected_db:
            st.info("Select a database to browse tables")
            return

        db_info = DATABASES[selected_db]
        if not os.path.exists(db_info["path"]):
            st.error(f"Database not found: {db_info['path']}")
            return

        tables = get_table_list(db_info["path"])
        if not tables:
            st.warning("No tables found in this database")
            return

        table_names = [t["table"] for t in tables]

        with col2:
            selected_table = st.selectbox("Select Table", table_names)

        if selected_table:
            # Schema
            st.subheader(f"Schema: {selected_db}.{selected_table}")
            schema = get_table_schema(db_info["path"], selected_table)
            st.dataframe(pd.DataFrame(schema), use_container_width=True, hide_index=True)

            # DDL
            with st.expander("📄 CREATE TABLE Statement"):
                ddl = get_create_statement(db_info["path"], selected_table)
                st.code(ddl, language="sql")

            # Data preview
            st.subheader("📋 Data Preview")
            row_limit = st.slider("Rows to show", 5, 200, 25, key="row_limit")
            df = get_table_data(db_info["path"], selected_table, row_limit)
            st.dataframe(df, use_container_width=True, hide_index=True)

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
                    st.dataframe(df, use_container_width=True, hide_index=True)
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
