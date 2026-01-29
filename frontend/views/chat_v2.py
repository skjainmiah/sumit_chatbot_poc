"""Chat V2 page - PostgreSQL with Full Schema approach and advanced visualization."""
import streamlit as st
import pandas as pd
from frontend.api_client import APIClient
from frontend.components.visualization import (
    render_visualization,
    render_chart_suggestions,
    analyze_data,
    get_unique_key,
)


def render_chat_v2():
    """Render the V2 chat interface with visualization support."""
    st.title("💬 Chat with Crew Assistant V2")
    st.caption("Ask about crew data, policies, schedules, and more")

    # Initialize API client
    client = APIClient(st.session_state.token)

    # Initialize v2-specific session state
    if "messages_v2" not in st.session_state:
        st.session_state.messages_v2 = []
    if "conversation_id_v2" not in st.session_state:
        st.session_state.conversation_id_v2 = None

    # Schema info in sidebar
    with st.sidebar:
        st.subheader("📊 V2 Schema Info")

        # Health check
        health = client.health_check_v2()
        if health.get("error"):
            st.error("V2 API not available")
            st.caption(f"Error: {health.get('detail', 'Unknown')}")
            st.info("Make sure backend is running")
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
                    st.caption(f"  ✓ {check_name}: {check_status}")
                else:
                    st.caption(f"  ✗ {check_name}: {check_status}")

        # Schema statistics
        schema_info = client.get_schema_info()
        if not schema_info.get("error") and schema_info.get("success"):
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Databases", len(schema_info.get('databases', [])))
            with col2:
                st.metric("Tables", schema_info.get('total_tables', 0))

            # Show database list
            with st.expander("📁 Available Databases"):
                for db in schema_info.get("databases", []):
                    st.write(f"• {db}")

        st.divider()

        # New conversation button
        if st.button("🔄 New V2 Conversation", use_container_width=True, key="new_conv_v2"):
            st.session_state.messages_v2 = []
            st.session_state.conversation_id_v2 = None
            st.rerun()

        # Reload schema button
        if st.button("🔃 Reload Schema", use_container_width=True, key="reload_schema"):
            result = client.reload_schema()
            if result.get("success"):
                st.success("Schema reloaded!")
            else:
                st.error(f"Failed: {result.get('error', 'Unknown')}")

        st.divider()

        # Quick tips
        with st.expander("💡 Visualization Tips"):
            st.markdown("""
            **For beautiful charts, try:**
            - "Show crew count by role as a chart"
            - "Compare payroll totals by month"
            - "Visualize flight status distribution"
            - "Show trend of training completions"

            **Keywords that trigger charts:**
            - `chart`, `graph`, `visualize`
            - `compare`, `trend`, `distribution`
            - `breakdown`, `proportion`
            """)

    # Display conversation history
    chat_container = st.container()

    with chat_container:
        for i, msg in enumerate(st.session_state.messages_v2):
            # Get preceding user query
            user_query = ""
            if msg.get("role") == "assistant" and i > 0:
                prev_msg = st.session_state.messages_v2[i - 1]
                if prev_msg.get("role") == "user":
                    user_query = prev_msg.get("content", "")

            render_message_v2(msg, user_query)

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
        context = build_context(st.session_state.messages_v2[-6:-1])

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
                "error": result.get("error"),
                "user_query": prompt,  # Store for visualization suggestions
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
        content = msg.get("content", "")[:200]
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


def render_message_v2(msg: dict, user_query: str = ""):
    """Render a single V2 chat message with visualization support."""
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
                    st.caption(":green[✓ Success]")
                elif msg.get("error"):
                    st.caption(":red[✗ Failed]")

            with col3:
                if msg.get("processing_time_ms"):
                    time_ms = msg.get("processing_time_ms")
                    if time_ms < 2000:
                        st.caption(f"⚡ :green[{time_ms}ms]")
                    elif time_ms < 5000:
                        st.caption(f"⏱️ :orange[{time_ms}ms]")
                    else:
                        st.caption(f"🐢 :red[{time_ms}ms]")

            # SQL Query display
            if msg.get("sql_query"):
                with st.expander("🔍 SQL Query", expanded=False):
                    st.code(msg.get("sql_query"), language="sql")

            # SQL Results display with visualization
            if msg.get("sql_results"):
                results = msg.get("sql_results")
                rows = results.get("rows", [])
                row_count = results.get("row_count", len(rows))

                if rows:
                    # Convert to DataFrame
                    df = pd.DataFrame(rows)

                    # Analyze for visualization suitability
                    analysis = analyze_data(df)
                    query_for_viz = user_query or msg.get("user_query", "")

                    # Check if user explicitly asked for visualization
                    viz_keywords = ["chart", "graph", "plot", "visualize", "trend", "compare", "distribution", "breakdown"]
                    wants_viz = any(kw in query_for_viz.lower() for kw in viz_keywords)

                    # Show chart suggestions for suitable data
                    if len(df) >= 2 and len(analysis["suitable_charts"]) > 1:
                        if wants_viz or len(df) <= 20:
                            render_chart_suggestions(
                                df,
                                query_for_viz,
                                key_prefix=get_unique_key("v2_suggest", results)
                            )

                    # Main results expander with visualization
                    with st.expander(f"📊 Results ({row_count} rows)", expanded=True):
                        if len(df) >= 2 and len(analysis["suitable_charts"]) > 1:
                            # Full visualization component
                            render_visualization(
                                df,
                                title=None,
                                key_prefix=get_unique_key("v2_viz", results),
                                show_selector=True,
                                default_expanded=wants_viz or len(df) <= 10,
                                allow_download=True
                            )
                        else:
                            # Simple data table
                            st.dataframe(df, use_container_width=True, hide_index=True)

                            # Download button
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download CSV",
                                data=csv,
                                file_name="query_results.csv",
                                mime="text/csv",
                                key=get_unique_key("v2_dl", results)
                            )

            # Clarification request
            if msg.get("clarification"):
                st.info(f"🤔 Clarification needed: {msg.get('clarification')}")

            # Error display
            if msg.get("error") and not msg.get("success"):
                st.error(f"Error: {msg.get('error')}")


def render_suggested_questions():
    """Render suggested questions based on schema."""
    st.subheader("Try asking:")
    suggestions = [
        "List available databases",
        "How many tables are there?",
        "Show crew count by role as a chart",
        "Compare payroll by month",
    ]

    cols = st.columns(2)
    for i, suggestion in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                return suggestion

    return None
