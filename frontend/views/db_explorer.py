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

        databases = {}
        for db_name, info in all_dbs.items():
            databases[db_name] = {
                "path": info["db_path"],
                "description": info.get("description", ""),
                "source_type": info.get("source_type", "unknown"),
                "is_visible": info.get("is_visible", True),
                "display_name": info.get("display_name", db_name)
            }

        # Add app database if not in registry
        if "app" not in databases:
            databases["app"] = {
                "path": settings.app_db_path,
                "description": "Users, conversations, messages, feedback, schema metadata, document chunks",
                "source_type": "system",
                "is_visible": False,
                "display_name": "App"
            }

        return databases
    except Exception:
        # Fallback to static config
        return {
            "crew_management": {
                "path": settings.crew_db_path,
                "description": "Crew members, qualifications, assignments, rest records, documents, contacts",
                "source_type": "mock",
                "is_visible": True,
                "display_name": "Crew Management"
            },
            "flight_operations": {
                "path": settings.flight_db_path,
                "description": "Airports, aircraft, flights, pairings, disruptions, hotels",
                "source_type": "mock",
                "is_visible": True,
                "display_name": "Flight Operations"
            },
            "hr_payroll": {
                "path": settings.hr_db_path,
                "description": "Pay grades, payroll records, leave, benefits, performance reviews, expenses",
                "source_type": "mock",
                "is_visible": True,
                "display_name": "HR Payroll"
            },
            "compliance_training": {
                "path": settings.compliance_db_path,
                "description": "Training courses/records, schedules, compliance checks, safety incidents, audit logs",
                "source_type": "mock",
                "is_visible": True,
                "display_name": "Compliance Training"
            },
            "app": {
                "path": settings.app_db_path,
                "description": "Users, conversations, messages, feedback, schema metadata, document chunks",
                "source_type": "system",
                "is_visible": False,
                "display_name": "App"
            },
        }


# Get databases dynamically
DATABASES = get_databases_from_registry()


def get_table_list(db_path):
    """Get all tables and row counts from a database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in c.fetchall()]
    result = []
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = c.fetchone()[0]
        result.append({"table": t, "rows": count})
    conn.close()
    return result


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
    st.title("Database Explorer")
    st.caption("Browse all databases, tables, schemas, and data")

    # Refresh databases from registry
    global DATABASES
    DATABASES = get_databases_from_registry()

    # --- Overview Tab and Detail Tab ---
    tab_overview, tab_detail, tab_schema_meta = st.tabs(["Overview", "Browse Tables", "Schema Metadata"])

    # ===== OVERVIEW TAB =====
    with tab_overview:
        st.subheader("Available Databases")
        for db_name, info in DATABASES.items():
            if db_name == "app":
                continue  # Skip internal app db from overview

            # Show visibility status
            visibility_icon = ":eye:" if info.get("is_visible", True) else ":no_entry_sign:"
            source_badge = ":package:" if info.get("source_type") == "mock" else ":arrow_up:" if info.get("source_type") == "uploaded" else ""
            display_name = info.get("display_name", db_name)

            with st.expander(f"{visibility_icon} **{display_name}** {source_badge} - {info['description']}", expanded=False):
                if os.path.exists(info["path"]):
                    tables = get_table_list(info["path"])
                    size_kb = os.path.getsize(info["path"]) / 1024
                    st.caption(f"Size: {size_kb:.0f} KB | Tables: {len(tables)}")
                    df = pd.DataFrame(tables)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.error(f"Database file not found: {info['path']}")

        # Summary metrics
        st.divider()
        st.subheader("Summary")
        total_tables = 0
        total_rows = 0
        for db_name, info in DATABASES.items():
            if db_name == "app" or not os.path.exists(info["path"]):
                continue
            tables = get_table_list(info["path"])
            total_tables += len(tables)
            total_rows += sum(t["rows"] for t in tables)

        col1, col2, col3 = st.columns(3)
        col1.metric("Databases", 4)
        col2.metric("Total Tables", total_tables)
        col3.metric("Total Rows", f"{total_rows:,}")

    # ===== BROWSE TABLES TAB =====
    with tab_detail:
        col1, col2 = st.columns([1, 2])

        with col1:
            selected_db = st.selectbox(
                "Select Database",
                [k for k in DATABASES.keys() if k != "app"],
                format_func=lambda x: x.replace("_", " ").title()
            )

        db_info = DATABASES[selected_db]
        if not os.path.exists(db_info["path"]):
            st.error("Database not found")
            return

        tables = get_table_list(db_info["path"])
        table_names = [t["table"] for t in tables]

        with col2:
            selected_table = st.selectbox("Select Table", table_names)

        if selected_table:
            # Schema
            st.subheader(f"Schema: {selected_db}.{selected_table}")
            schema = get_table_schema(db_info["path"], selected_table)
            st.dataframe(pd.DataFrame(schema), use_container_width=True, hide_index=True)

            # DDL
            with st.expander("CREATE TABLE Statement"):
                ddl = get_create_statement(db_info["path"], selected_table)
                st.code(ddl, language="sql")

            # Data preview
            st.subheader("Data Preview")
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
            conn = sqlite3.connect(settings.app_db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM schema_metadata")
            count = c.fetchone()[0]

            if count > 0:
                df = pd.read_sql_query(
                    "SELECT db_name, table_name, llm_description, row_count, last_crawled_at FROM schema_metadata ORDER BY db_name, table_name",
                    conn
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"{count} table schemas indexed")
            else:
                st.warning("Schema metadata is empty. Run the setup to populate it:")
                st.code("python scripts/run_all_setup.py", language="bash")
                st.info("Note: Schema crawling requires a valid OpenAI API key to generate table descriptions and embeddings.")
            conn.close()
        else:
            st.error("App database not found")
