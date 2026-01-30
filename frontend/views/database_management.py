"""Database Management UI - upload SQL files and manage database visibility."""
import streamlit as st
import pandas as pd
import json
from frontend.api_client import APIClient


def render_database_management():
    """Render the database management panel for admins."""
    # Check if user is admin
    if not st.session_state.user or st.session_state.user.get("role") != "admin":
        st.error("Access denied. Admin privileges required.")
        return

    st.subheader("Database Management")

    client = APIClient(st.session_state.token)

    # Three sections: Upload SQL, Upload CSV/Excel, Visibility
    upload_section, csv_section, visibility_section = st.tabs(
        ["Upload SQL File", "Upload CSV / Excel", "Database Visibility"]
    )

    with upload_section:
        render_upload_section(client)

    with csv_section:
        render_csv_upload_section(client)

    with visibility_section:
        render_visibility_section(client)


def render_upload_section(client: APIClient):
    """Render the SQL file upload section."""
    st.markdown("### Upload SQL Dump File")
    st.caption(
        "Upload a .sql file to create a new SQLite database. "
        "Supports **PostgreSQL** (pg_dump/pg_dumpall) and **Microsoft SQL Server** (SSMS scripts)."
    )

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a .sql file",
        type=["sql"],
        help="Maximum file size: 100MB. Auto-detects PostgreSQL or MSSQL syntax."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        auto_visible = st.checkbox(
            "Make database visible after upload",
            value=True,
            help="If checked, the new database will be included in chat queries immediately."
        )

    if uploaded_file is not None:
        st.info(f"Selected file: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

        if st.button("Upload and Process", type="primary"):
            with st.spinner("Processing SQL file..."):
                result = client.upload_sql_file(uploaded_file, auto_visible=auto_visible)

                if result.get("error"):
                    st.error(f"Upload failed: {result.get('detail', 'Unknown error')}")
                elif result.get("success"):
                    dialect = result.get("dialect", "unknown")
                    st.success(f"Upload completed successfully! Detected dialect: **{dialect.upper()}**")

                    # Show created databases
                    databases = result.get("databases_created", [])
                    if databases:
                        st.markdown("**Created Databases:**")
                        for db in databases:
                            st.markdown(
                                f"- **{db['db_name']}**: {db['tables_created']} tables, "
                                f"{db['rows_inserted']} rows"
                            )
                        st.info("Schema metadata populated and FAISS index rebuilt automatically.")

                    # Show warnings if any
                    warnings = result.get("warnings", [])
                    if warnings:
                        with st.expander("Warnings"):
                            for w in warnings:
                                st.warning(w)
                else:
                    errors = result.get("errors", ["Unknown error"])
                    st.error(f"Upload failed: {errors[0]}")

    # Upload history
    st.divider()
    st.markdown("### Upload History")

    history = client.get_upload_history(limit=10)

    if isinstance(history, dict) and history.get("error"):
        st.warning("Could not load upload history")
    elif not history:
        st.info("No upload history yet")
    else:
        history_data = []
        for h in history:
            status_icon = {
                "completed": ":white_check_mark:",
                "processing": ":hourglass_flowing_sand:",
                "failed": ":x:"
            }.get(h.get("status"), ":question:")

            history_data.append({
                "Status": status_icon,
                "Filename": h.get("filename", "N/A"),
                "Tables": h.get("tables_created", 0),
                "Date": h.get("created_at", "")[:16],
                "Error": (h.get("error_message") or "")[:50]
            })

        if history_data:
            df = pd.DataFrame(history_data)
            st.dataframe(df, width="stretch", hide_index=True)


def render_csv_upload_section(client: APIClient):
    """Render the CSV/Excel file upload section."""
    st.markdown("### Upload CSV / Excel Files")
    st.caption(
        "Upload `.csv`, `.xlsx`, or `.xls` files to create database tables. "
        "Each file becomes a separate table (filename is used as the table name)."
    )

    # File uploader
    uploaded_files = st.file_uploader(
        "Choose CSV or Excel files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        help="You can upload multiple files at once. Each file becomes a table.",
        key="csv_uploader"
    )

    # Database target selection
    db_mode = st.radio(
        "Target database",
        ["Create new database", "Add to existing database"],
        key="csv_db_mode",
        horizontal=True
    )

    db_name = ""
    if db_mode == "Create new database":
        db_name = st.text_input(
            "Database name",
            placeholder="e.g. sales_data",
            help="Letters, numbers, and underscores only. Will be lowercased.",
            key="csv_db_name"
        )
    else:
        # List existing uploaded databases
        result = client.list_databases(include_hidden=True)
        if result.get("error"):
            st.error("Could not load databases")
            return
        databases = result.get("databases", [])
        uploaded_dbs = [
            db["db_name"] for db in databases
            if db.get("source_type") == "uploaded"
        ]
        if not uploaded_dbs:
            st.warning("No uploaded databases found. Create a new one instead.")
            return
        db_name = st.selectbox(
            "Select database",
            options=uploaded_dbs,
            key="csv_existing_db"
        )

    is_new_db = db_mode == "Create new database"

    auto_visible = st.checkbox(
        "Make database visible after upload",
        value=True,
        help="If checked, the database will be available for chat queries immediately.",
        key="csv_auto_visible"
    )

    if uploaded_files:
        st.info(f"**{len(uploaded_files)} file(s) selected:** " +
                ", ".join(f.name for f in uploaded_files))

        if st.button("Upload and Process", type="primary", key="csv_upload_btn"):
            if not db_name or not db_name.strip():
                st.error("Please enter a database name.")
                return

            with st.spinner("Processing files..."):
                result = client.upload_csv_files(
                    files=uploaded_files,
                    db_name=db_name,
                    is_new_db=is_new_db,
                    auto_visible=auto_visible
                )

                if result.get("error"):
                    st.error(f"Upload failed: {result.get('detail', 'Unknown error')}")
                elif result.get("success"):
                    st.success(
                        f"Upload completed! "
                        f"**{result.get('total_tables', 0)} table(s)** created with "
                        f"**{result.get('total_rows', 0):,} total rows**."
                    )

                    # Show created databases/tables
                    databases = result.get("databases_created", [])
                    if databases:
                        for db in databases:
                            st.markdown(
                                f"- Database **{db['db_name']}**: "
                                f"{db['tables_created']} tables, "
                                f"{db['rows_inserted']:,} rows"
                            )
                        st.info("Schema metadata populated and indexes rebuilt automatically.")

                    # Show warnings
                    warnings = result.get("warnings", [])
                    if warnings:
                        with st.expander("Warnings"):
                            for w in warnings:
                                st.warning(w)

                    # Show errors (partial failures)
                    errors = result.get("errors", [])
                    if errors:
                        with st.expander("Errors"):
                            for e in errors:
                                st.error(e)
                else:
                    errors = result.get("errors", ["Unknown error"])
                    st.error(f"Upload failed: {errors[0]}")


def render_visibility_section(client: APIClient):
    """Render the database visibility management section."""
    st.markdown("### Database Visibility")
    st.caption(
        "Control which databases are visible. "
        "Unchecked databases will be hidden from Chat, Database Explorer, and LLM schema context."
    )

    # Fetch database list
    result = client.list_databases(include_hidden=True)

    if result.get("error"):
        st.error(f"Failed to load databases: {result.get('detail')}")
        return

    databases = result.get("databases", [])
    if not databases:
        st.warning("No databases registered. Run database setup first.")
        return

    # Show stats
    visible_count = result.get("visible_count", 0)
    total_count = result.get("total", 0)
    st.info(f"**{visible_count}** of **{total_count}** databases visible to chat")

    st.divider()

    # Group by source type
    mock_dbs = [db for db in databases if db.get("source_type") == "mock"]
    uploaded_dbs = [db for db in databases if db.get("source_type") == "uploaded"]

    # Mock databases section
    if mock_dbs:
        st.markdown("#### Built-in Databases")
        for db in mock_dbs:
            render_database_row(client, db, can_delete=False)

    # Uploaded databases section
    if uploaded_dbs:
        st.markdown("#### Uploaded Databases")
        for db in uploaded_dbs:
            render_database_row(client, db, can_delete=True)

    # Warning about minimum visibility
    st.divider()
    st.caption(
        ":information_source: At least one database must remain visible. "
        "Mock databases can be hidden but not deleted."
    )


def _toggle_visibility(client: APIClient, db_name: str, key: str):
    """Callback for visibility checkbox — updates backend without st.rerun()."""
    new_val = st.session_state[key]
    client.set_database_visibility(db_name, new_val)


def render_database_row(client: APIClient, db: dict, can_delete: bool = False):
    """Render a single database row with visibility toggle."""
    db_name = db.get("db_name", "Unknown")
    display_name = db.get("display_name") or db_name
    description = db.get("description", "")
    table_count = db.get("table_count", 0)
    is_visible = db.get("is_visible", True)
    source_type = db.get("source_type", "unknown")

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        source_badge = ":package:" if source_type == "mock" else ":arrow_up:"
        visibility_icon = ":eye:" if is_visible else ":no_entry_sign:"
        desc_text = f"{description[:80]}..." if len(description) > 80 else description
        st.markdown(
            f"{visibility_icon} **{display_name}** {source_badge}\n\n<small>{desc_text}</small>",
            unsafe_allow_html=True
        )

    with col2:
        st.caption(f"{table_count} tables")

        checkbox_key = f"vis_{db_name}"
        # Initialize session state from API value to avoid mismatch
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = is_visible

        st.checkbox(
            "Visible",
            key=checkbox_key,
            on_change=_toggle_visibility,
            args=(client, db_name, checkbox_key),
            help="Include in Chat, Explorer, and LLM context"
        )

    with col3:
        if can_delete:
            confirm_key = f"confirm_delete_{db_name}"
            if st.button("Delete", key=f"del_{db_name}", help="Delete database"):
                st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key):
                col_y, col_n = st.columns(2)
                with col_y:
                    if st.button("Yes", key=f"yes_{db_name}"):
                        result = client.delete_database(db_name)
                        if isinstance(result, dict) and result.get("error"):
                            st.error(result.get("detail"))
                        else:
                            st.success(f"Deleted {db_name}")
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                with col_n:
                    if st.button("No", key=f"no_{db_name}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
        else:
            st.caption("(built-in)")
