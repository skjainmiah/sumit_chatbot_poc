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

    # Two sections: Upload and Visibility
    upload_section, visibility_section = st.tabs(["Upload SQL File", "Database Visibility"])

    with upload_section:
        render_upload_section(client)

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

    if history.get("error"):
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
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_visibility_section(client: APIClient):
    """Render the database visibility management section."""
    st.markdown("### Database Visibility")
    st.caption(
        "Control which databases are included in chat queries. "
        "Unchecked databases will be hidden from the chatbot but still accessible in the Database Explorer."
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
        # Database info
        source_badge = ":package:" if source_type == "mock" else ":arrow_up:"
        visibility_status = ":eye:" if is_visible else ":no_entry_sign:"

        st.markdown(
            f"{visibility_status} **{display_name}** {source_badge}\n\n"
            f"<small>{description[:80]}...</small>" if len(description) > 80 else f"{visibility_status} **{display_name}** {source_badge}\n\n<small>{description}</small>",
            unsafe_allow_html=True
        )

    with col2:
        st.caption(f"{table_count} tables")

        # Visibility toggle
        new_visibility = st.checkbox(
            "Visible",
            value=is_visible,
            key=f"vis_{db_name}",
            help="Include in chat queries"
        )

        if new_visibility != is_visible:
            result = client.set_database_visibility(db_name, new_visibility)
            if result.get("error"):
                st.error(result.get("detail", "Failed to update"))
            else:
                st.rerun()

    with col3:
        if can_delete:
            if st.button(":wastebasket:", key=f"del_{db_name}", help="Delete database"):
                # Confirmation in session state
                if st.session_state.get(f"confirm_delete_{db_name}"):
                    result = client.delete_database(db_name)
                    if result.get("error"):
                        st.error(result.get("detail"))
                    else:
                        st.success(f"Deleted {db_name}")
                        st.session_state.pop(f"confirm_delete_{db_name}", None)
                        st.rerun()
                else:
                    st.session_state[f"confirm_delete_{db_name}"] = True
                    st.warning("Click again to confirm deletion")
        else:
            st.caption("(protected)")
