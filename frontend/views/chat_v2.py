"""Chat V2 page - PostgreSQL with Full Schema approach."""
import streamlit as st
import pandas as pd
from frontend.api_client import APIClient


def render_chat_v2():
    """Render the V2 chat interface (PostgreSQL)."""
    st.title("Chat V2 (PostgreSQL)")
    st.caption("Full schema approach - faster and more accurate")

    # Initialize API client
    client = APIClient(st.session_state.token)

    # Initialize v2-specific session state
    if "messages_v2" not in st.session_state:
        st.session_state.messages_v2 = []
    if "conversation_id_v2" not in st.session_state:
        st.session_state.conversation_id_v2 = None

    # Schema info in sidebar
    with st.sidebar:
        st.subheader("V2 Schema Info")

        # Health check
        health = client.health_check_v2()
        if health.get("error"):
            st.error("V2 API not available")
            st.caption(f"Error: {health.get('detail', 'Unknown')}")
            st.info("Make sure backend is running with PostgreSQL configured")
            return
        else:
            status = health.get("status", "unknown")
            if status == "healthy":
                st.success(f"Status: {status}")
            else:
                st.warning(f"Status: {status}")

            checks = health.get("checks", {})
            for check_name, check_status in checks.items():
                if "ok" in str(check_status).lower():
                    st.caption(f"  {check_name}: {check_status}")
                else:
                    st.caption(f"  {check_name}: {check_status}")

        # Schema statistics
        schema_info = client.get_schema_info()
        if not schema_info.get("error") and schema_info.get("success"):
            st.divider()
            st.caption(f"Databases: {len(schema_info.get('databases', []))}")
            st.caption(f"Tables: {schema_info.get('total_tables', 0)}")
            st.caption(f"Columns: {schema_info.get('total_columns', 0)}")
            st.caption(f"Est. tokens: {schema_info.get('estimated_tokens', 0):,}")

            # Show database list
            with st.expander("Available Databases"):
                for db in schema_info.get("databases", []):
                    st.write(f"- {db}")

        st.divider()

        # New conversation button
        if st.button("New V2 Conversation", use_container_width=True, key="new_conv_v2"):
            st.session_state.messages_v2 = []
            st.session_state.conversation_id_v2 = None
            st.rerun()

        # Reload schema button
        if st.button("Reload Schema", use_container_width=True, key="reload_schema"):
            result = client.reload_schema()
            if result.get("success"):
                st.success("Schema reloaded!")
            else:
                st.error(f"Failed: {result.get('error', 'Unknown')}")

    # Display conversation history
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.messages_v2:
            render_message_v2(msg)

    # Chat input
    if prompt := st.chat_input("Ask about your databases...", key="chat_input_v2"):
        # Add user message
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages_v2.append(user_msg)

        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.write(prompt)

        # Build context from recent messages
        context = build_context(st.session_state.messages_v2[-6:-1])  # Last 5 messages before current

        # Send to backend
        with st.spinner("Querying..."):
            result = client.send_message_v2(
                prompt,
                st.session_state.conversation_id_v2,
                context
            )

        if result.get("error"):
            st.error(f"Error: {result.get('detail', 'Unknown error')}")
        else:
            # Update conversation ID
            st.session_state.conversation_id_v2 = result.get("conversation_id")

            # Create assistant message
            assistant_msg = {
                "role": "assistant",
                "content": result.get("response", ""),
                "intent": result.get("intent"),
                "sql_query": result.get("sql_query"),
                "sql_results": result.get("sql_results"),
                "clarification": result.get("clarification"),
                "processing_time_ms": result.get("processing_time_ms"),
                "success": result.get("success", False),
                "error": result.get("error")
            }
            st.session_state.messages_v2.append(assistant_msg)

            # Rerun to display
            st.rerun()


def build_context(messages: list) -> str:
    """Build context string from recent messages."""
    if not messages:
        return ""

    context_parts = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")[:200]  # Truncate
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


def render_message_v2(msg: dict):
    """Render a single V2 chat message."""
    role = msg.get("role", "user")

    with st.chat_message(role):
        # Main content
        st.write(msg.get("content", ""))

        if role == "assistant":
            # Intent and status badges
            intent = msg.get("intent", "")
            success = msg.get("success", True)

            col1, col2, col3 = st.columns([1, 1, 2])

            with col1:
                intent_colors = {
                    "meta": "blue",
                    "data": "green",
                    "ambiguous": "orange",
                    "general": "gray",
                    "error": "red"
                }
                color = intent_colors.get(intent, "gray")
                st.caption(f"Intent: :{color}[{intent}]")

            with col2:
                if success:
                    st.caption(":green[Success]")
                elif msg.get("error"):
                    st.caption(":red[Failed]")

            with col3:
                if msg.get("processing_time_ms"):
                    time_ms = msg.get("processing_time_ms")
                    if time_ms < 2000:
                        st.caption(f":green[{time_ms}ms]")
                    elif time_ms < 5000:
                        st.caption(f":orange[{time_ms}ms]")
                    else:
                        st.caption(f":red[{time_ms}ms]")

            # SQL Query display
            if msg.get("sql_query"):
                with st.expander("SQL Query", expanded=False):
                    st.code(msg.get("sql_query"), language="sql")

            # SQL Results display
            if msg.get("sql_results"):
                results = msg.get("sql_results")
                rows = results.get("rows", [])
                row_count = results.get("row_count", len(rows))

                if rows:
                    with st.expander(f"Results ({row_count} rows)", expanded=True):
                        # Convert to DataFrame for nice display
                        df = pd.DataFrame(rows)
                        st.dataframe(df, use_container_width=True, hide_index=True)

                        # Download button
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name="query_results.csv",
                            mime="text/csv",
                            key=f"download_{id(msg)}"
                        )

            # Clarification request
            if msg.get("clarification"):
                st.info(f"Clarification needed: {msg.get('clarification')}")

            # Error display
            if msg.get("error") and not msg.get("success"):
                st.error(f"Error: {msg.get('error')}")


def render_suggested_questions():
    """Render suggested questions based on schema."""
    st.subheader("Try asking:")
    suggestions = [
        "List available databases",
        "How many tables are there?",
        "Show all tables in hr_db",
        "What columns are in the employees table?",
    ]

    cols = st.columns(2)
    for i, suggestion in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                return suggestion

    return None
