"""Admin panel page."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from frontend.api_client import APIClient
from frontend.views.database_management import render_database_management


def render_admin():
    """Render the admin panel."""
    # Check if user is admin
    if not st.session_state.user or st.session_state.user.get("role") != "admin":
        st.error("Access denied. Admin privileges required.")
        return

    st.title("Admin Panel")

    client = APIClient(st.session_state.token)

    # Tabs for different admin functions
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "Users", "Feedback", "Databases", "PII Masking"])

    with tab1:
        render_dashboard(client)

    with tab2:
        render_users(client)

    with tab3:
        render_feedback(client)

    with tab4:
        render_database_management()

    with tab5:
        render_pii_settings(client)


def render_dashboard(client: APIClient):
    """Render the admin dashboard with statistics."""
    st.subheader("Usage Statistics")

    stats = client.get_stats()

    if isinstance(stats, dict) and stats.get("error"):
        st.error(f"Failed to load statistics: {stats.get('detail')}")
        return

    if not isinstance(stats, dict):
        st.error("Unexpected response from server")
        return

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Users", stats.get("total_users", 0))
    with col2:
        st.metric("Total Conversations", stats.get("total_conversations", 0))
    with col3:
        st.metric("Total Messages", stats.get("total_messages", 0))
    with col4:
        st.metric("Avg Response Time", f"{stats.get('avg_response_time_ms', 0):.0f}ms")

    st.divider()

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Intent distribution chart
        st.subheader("Intent Distribution")
        intent_data = stats.get("intent_distribution", {})
        if intent_data:
            fig = px.pie(
                values=list(intent_data.values()),
                names=list(intent_data.keys()),
                title="Query Intent Distribution",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No intent data available")

    with col2:
        # Feedback distribution chart
        st.subheader("Feedback Distribution")
        feedback_data = stats.get("feedback_distribution", {})
        if feedback_data:
            colors = {"thumbs_up": "#2ecc71", "thumbs_down": "#e74c3c"}
            fig = go.Figure(data=[
                go.Bar(
                    x=list(feedback_data.keys()),
                    y=list(feedback_data.values()),
                    marker_color=[colors.get(k, "#3498db") for k in feedback_data.keys()]
                )
            ])
            fig.update_layout(title="User Feedback")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No feedback data available")

    # Messages over time
    st.subheader("Activity Over Time")
    daily_stats = stats.get("daily_messages", [])
    if daily_stats:
        df = pd.DataFrame(daily_stats)
        fig = px.line(
            df,
            x="date",
            y="count",
            title="Messages Per Day",
            markers=True
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No activity data available")


def render_users(client: APIClient):
    """Render user management section."""
    st.subheader("User Management")

    result = client.list_users()

    if isinstance(result, dict) and result.get("error"):
        st.error(f"Failed to load users: {result.get('detail')}")
        return

    user_list = result if isinstance(result, list) else []
    if not user_list:
        st.info("No users found")
        return

    # Convert to DataFrame for display
    df = pd.DataFrame(user_list)

    # Display columns we want
    display_cols = ["user_id", "username", "email", "full_name", "role", "is_active", "created_at"]
    available_cols = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[available_cols],
        width="stretch",
        hide_index=True
    )

    st.caption(f"Total users: {len(user_list)}")


def render_feedback(client: APIClient):
    """Render feedback review section."""
    st.subheader("User Feedback")

    # Filter options
    col1, col2 = st.columns([1, 3])
    with col1:
        rating_filter = st.selectbox(
            "Filter by rating",
            ["All", "thumbs_up", "thumbs_down"]
        )

    # Get feedback
    rating_param = None if rating_filter == "All" else rating_filter
    feedback_result = client.list_feedback(rating=rating_param, limit=100)

    if isinstance(feedback_result, dict) and feedback_result.get("error"):
        st.error(f"Failed to load feedback: {feedback_result.get('detail')}")
        return

    feedback_list = feedback_result if isinstance(feedback_result, list) else []
    if not feedback_list:
        st.info("No feedback found")
        return

    # Display feedback
    for fb in feedback_list:
        with st.expander(
            f"{'👍' if fb.get('rating') == 'thumbs_up' else '👎'} Message #{fb.get('message_id')} - {fb.get('created_at', 'Unknown date')}"
        ):
            st.write(f"**User:** {fb.get('username', 'Unknown')}")
            st.write(f"**Rating:** {fb.get('rating')}")
            if fb.get("comment"):
                st.write(f"**Comment:** {fb.get('comment')}")
            if fb.get("message_content"):
                st.write("**Message:**")
                st.text(fb.get("message_content"))

    st.caption(f"Total feedback items: {len(feedback_list)}")


def render_pii_settings(client: APIClient):
    """Render PII masking configuration UI."""
    st.subheader("PII Masking Configuration")
    st.caption("Control how sensitive information (emails, phone numbers, SSNs, etc.) is masked before being sent to the LLM.")

    # Load current settings
    result = client.get_pii_settings()

    if isinstance(result, dict) and result.get("error"):
        st.error(f"Failed to load PII settings: {result.get('detail', 'Unknown error')}")
        return

    # Main toggles
    col1, col2 = st.columns(2)
    with col1:
        pii_enabled = st.toggle(
            "Enable PII Masking",
            value=result.get("enabled", True),
            help="When enabled, sensitive data is replaced with tokens (e.g., [EMAIL_1]) before sending to the LLM",
            key="pii_toggle_enabled"
        )
    with col2:
        log_enabled = st.toggle(
            "Enable PII Audit Logging",
            value=result.get("log_enabled", True),
            help="When enabled, detailed logs show user input, masked input, LLM output, and final response for PII verification",
            key="pii_toggle_log"
        )

    st.divider()

    # Pattern toggles
    st.markdown("**Select PII types to mask:**")
    patterns = result.get("patterns", {})

    pattern_states = {}
    cols = st.columns(3)
    for i, (pii_type, info) in enumerate(patterns.items()):
        with cols[i % 3]:
            pattern_states[pii_type] = st.checkbox(
                info.get('label', pii_type),
                value=info.get('enabled', True),
                key=f"pii_pattern_{pii_type}",
                disabled=not pii_enabled
            )

    st.divider()

    # Save button
    if st.button("Save PII Settings", key="pii_save_btn", type="primary"):
        save_result = client.update_pii_settings(
            enabled=pii_enabled,
            log_enabled=log_enabled,
            patterns=pattern_states
        )
        if isinstance(save_result, dict) and save_result.get("success"):
            st.success("PII settings saved successfully!")
        else:
            st.error(f"Failed to save: {save_result.get('detail', 'Unknown error')}")

    # How it works section
    st.divider()
    with st.expander("How PII Masking Works", expanded=False):
        st.markdown("""
**Pipeline:**
1. **User Input** - User sends a message (e.g., "Show data for john.doe@aa.com")
2. **PII Detection** - Regex patterns detect sensitive data
3. **Masking** - PII is replaced with tokens: `"Show data for [EMAIL_1]"`
4. **LLM Processing** - The masked text is sent to the LLM (no real PII exposed)
5. **LLM Response** - LLM responds using the tokens: `"Data for [EMAIL_1]: ..."`
6. **Unmasking** - Tokens are restored: `"Data for john.doe@aa.com: ..."`
7. **Final Response** - User sees the complete response with original values

**Audit Logs** (when enabled) record each step so you can verify PII never reaches the LLM in plain text.
Check the backend logs for entries tagged with `[PII]`.
        """)
