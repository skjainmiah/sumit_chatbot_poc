"""Chat V2 page - uses full schema approach with advanced visualization."""
import random
import streamlit as st
import pandas as pd
from frontend.api_client import APIClient
from frontend.components.visualization import (
    render_visualization,
    render_chart_suggestions,
    analyze_data,
    get_unique_key,
    reset_key_counts,
)
from frontend.components.loading_facts import show_loading_with_facts


# ==========================================
# Visitor-name helpers
# ==========================================

def _is_greeting(text: str) -> bool:
    """Return True when the message is purely a greeting."""
    lower = text.strip().lower().rstrip(".,!?")
    greetings = {
        "hi", "hello", "hey", "howdy", "greetings", "good morning",
        "good afternoon", "good evening", "sup", "yo", "hi there",
        "hello there", "hey there", "hola", "namaste",
    }
    return lower in greetings


def _extract_name(text: str):
    """Extract just the first name from input like 'I'm Jainmiah' or 'My name is John Smith'.

    Returns the capitalised first name, or None if the input doesn't look like a name.
    """
    text = text.strip()
    lower = text.lower()

    prefixes = [
        "my name is ", "i'm ", "i am ", "it's ", "its ",
        "call me ", "they call me ", "you can call me ",
        "this is ", "hi i'm ", "hello i'm ", "hey i'm ",
        "hi i am ", "hello i am ", "hey i am ", "i'm called ",
        "people call me ", "just call me ", "please call me ",
        "hi, i'm ", "hello, i'm ", "hey, i'm ",
        "hi, i am ", "hello, i am ", "hey, i am ",
    ]

    for prefix in prefixes:
        if lower.startswith(prefix):
            text = text[len(prefix):]
            break

    text = text.strip().rstrip(".,!?")

    words = text.split()
    if len(words) > 3 or "?" in text:
        return None

    if words:
        name = words[0]
        return name[0].upper() + name[1:] if len(name) > 1 else name.upper()
    return None


def _is_name_change_request(text: str):
    """Return (True, new_name) if the user wants to change their name, else (False, None)."""
    lower = text.strip().lower()
    patterns = [
        "change my name to ", "rename me to ",
        "please call me ", "update my name to ",
        "i want to be called ", "call me ",
        "my name is actually ", "actually my name is ",
        "actually i'm ", "actually i am ",
    ]
    for pattern in patterns:
        if lower.startswith(pattern):
            raw = text.strip()[len(pattern):]
            name = _extract_name(raw)
            if name:
                return True, name
    return False, None


def _init_visitor_name_v2(client: APIClient):
    """Check DB for a stored visitor name on first page load."""
    if "visitor_name_checked" in st.session_state:
        return
    st.session_state["visitor_name_checked"] = True
    try:
        result = client.get_visitor_name()
        if result.get("name"):
            st.session_state["visitor_name"] = result["name"]
        else:
            st.session_state["needs_name"] = True
    except Exception:
        pass


# ==========================================
# Main page
# ==========================================

def render_chat_v2():
    """Main V2 chat page - handles message display, schema info sidebar, and query submission."""
    st.title("Chat with Crew Assistant V2")
    st.caption("Ask about crew data, policies, schedules, and more")

    # Initialize API client
    client = APIClient(st.session_state.token)

    # Visitor name greeting
    _init_visitor_name_v2(client)

    # Initialize v2-specific session state
    if "messages_v2" not in st.session_state:
        st.session_state.messages_v2 = []
    if "conversation_id_v2" not in st.session_state:
        st.session_state.conversation_id_v2 = None

    # Schema info in sidebar
    with st.sidebar:
        visitor_name = st.session_state.get("visitor_name")
        if visitor_name:
            st.caption(f"👤 Hi, {visitor_name}")
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
        if st.button("🔄 New V2 Conversation", width="stretch", key="new_conv_v2"):
            st.session_state.messages_v2 = []
            st.session_state.conversation_id_v2 = None
            st.rerun()

        # Reload schema button
        if st.button("🔃 Reload Schema", width="stretch", key="reload_schema"):
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
    reset_key_counts()

    with chat_container:
        # Welcome back for returning users (empty conversation only)
        if not st.session_state.messages_v2:
            visitor_name = st.session_state.get("visitor_name")
            if visitor_name:
                with st.chat_message("assistant", avatar=None):
                    st.write(f"Welcome back, {visitor_name}!")

        for i, msg in enumerate(st.session_state.messages_v2):
            # Get preceding user query
            user_query = ""
            if msg.get("role") == "assistant" and i > 0:
                prev_msg = st.session_state.messages_v2[i - 1]
                if prev_msg.get("role") == "user":
                    user_query = prev_msg.get("content", "")

            render_message_v2(msg, user_query, message_index=i)

    # Handle pending suggestion clicks
    pending = st.session_state.pop("v2_pending_suggestion", None)

    # Chat input
    if prompt := (pending or st.chat_input("Ask about your databases...", key="chat_input_v2")):

        # --- 1. Name-change request (only when a name is already stored) ---
        if st.session_state.get("visitor_name"):
            is_change, new_name = _is_name_change_request(prompt)
            if is_change and new_name:
                st.session_state["visitor_name"] = new_name
                try:
                    client.set_visitor_name(new_name)
                except Exception:
                    pass
                st.session_state.messages_v2.append({"role": "user", "content": prompt})
                st.session_state.messages_v2.append({
                    "role": "assistant",
                    "content": f"Sure! I'll call you {new_name} from now on.",
                })
                st.rerun()
                return

        # --- 2. Bot already asked for name — capture the reply ---
        if st.session_state.get("awaiting_name"):
            name = _extract_name(prompt)
            if name:
                st.session_state["visitor_name"] = name
                st.session_state.pop("awaiting_name", None)
                st.session_state.pop("needs_name", None)
                try:
                    client.set_visitor_name(name)
                except Exception:
                    pass
                st.session_state.messages_v2.append({"role": "user", "content": prompt})
                if st.session_state.pop("greeting_name_ask", False):
                    st.session_state.messages_v2.append({
                        "role": "assistant",
                        "content": f"Hello, {name}! How can I help you today?",
                    })
                else:
                    st.session_state.messages_v2.append({
                        "role": "assistant",
                        "content": f"Thanks, {name}! Feel free to ask me anything.",
                    })
                st.rerun()
                return
            else:
                # Doesn't look like a name — clear flag and process normally
                st.session_state.pop("awaiting_name", None)
                st.session_state.pop("greeting_name_ask", None)

        # --- 3. First message & we still need a name ---
        has_user_msgs = any(m.get("role") == "user" for m in st.session_state.messages_v2)
        if st.session_state.get("needs_name") and not has_user_msgs:
            if _is_greeting(prompt):
                st.session_state.messages_v2.append({"role": "user", "content": prompt})
                st.session_state.messages_v2.append({
                    "role": "assistant",
                    "content": "Hello! Can I know your good name?",
                })
                st.session_state["awaiting_name"] = True
                st.session_state["greeting_name_ask"] = True
                st.rerun()
                return
            else:
                st.session_state["ask_name_after_response"] = True

        # --- Normal message flow ---
        # Track message count for suggestion randomization
        st.session_state["v2_msg_count"] = st.session_state.get("v2_msg_count", 0) + 1

        # Add user message
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages_v2.append(user_msg)

        # Display user message
        with chat_container:
            with st.chat_message("user", avatar=None):
                st.write(prompt)

        # Auto-scroll to show the user's question above the input bar
        st.markdown(
            "<script>window.parent.document.querySelector('section.main').scrollTo(0, 999999)</script>",
            unsafe_allow_html=True,
        )

        # Build context from recent messages
        context = build_context(st.session_state.messages_v2[-6:-1])

        # Send to backend with loading animation
        loading_placeholder = st.empty()
        stop_event = show_loading_with_facts(loading_placeholder)
        try:
            result = client.send_message_v2(
                prompt,
                st.session_state.conversation_id_v2,
                context
            )
        finally:
            stop_event.set()
            loading_placeholder.empty()

        # Distinguish HTTP/connection errors (error=True) from application-level errors
        is_http_error = result.get("error") is True

        if is_http_error:
            st.error(f"Error: {result.get('detail', 'Unknown error')}")
        else:
            # Update conversation ID
            st.session_state.conversation_id_v2 = result.get("conversation_id")

            content = result.get("response", "")

            # Append name question if this was the first question and we need a name
            if st.session_state.pop("ask_name_after_response", False):
                content += "\n\nBy the way, can I know your good name?"
                st.session_state["awaiting_name"] = True

            # Create assistant message (works for both success and application-level errors)
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "intent": result.get("intent"),
                "sql_query": result.get("sql_query"),
                "sql_results": result.get("sql_results"),
                "clarification": result.get("clarification"),
                "suggestions": result.get("suggestions"),
                "processing_time_ms": result.get("processing_time_ms"),
                "success": result.get("success", False),
                "error": result.get("error"),
                "user_query": prompt,
            }
            st.session_state.messages_v2.append(assistant_msg)

            # Rerun to display
            st.rerun()


def build_context(messages: list) -> str:
    """Builds a short context string from the last few messages for the LLM."""
    if not messages:
        return ""

    context_parts = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")[:200]
        context_parts.append(f"{role}: {content}")

    return "\n".join(context_parts)


def render_message_v2(msg: dict, user_query: str = "", message_index: int = 0):
    """Shows one chat message - user or assistant - with charts, SQL, and suggestions."""
    role = msg.get("role", "user")

    with st.chat_message(role, avatar=None):
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
                    viz_keywords = ["chart", "graph", "plot", "visualize", "trend", "compare", "distribution",
                                    "breakdown", "count", "total", "sum", "average", "how many", "number of", "table"]
                    wants_viz = any(kw in query_for_viz.lower() for kw in viz_keywords)

                    has_charts = len(analysis["suitable_charts"]) > 1

                    # Auto-render chart inline when viz keywords detected
                    if has_charts and wants_viz:
                        render_chart_suggestions(
                            df,
                            query_for_viz,
                            key_prefix=get_unique_key("v2_suggest", results)
                        )

                    # Check if user asked for a specific chart type that doesn't suit the data
                    chart_type_keywords = {"bar": "bar", "pie": "pie", "line": "line", "donut": "donut", "scatter": "scatter"}
                    for kw, ctype in chart_type_keywords.items():
                        if kw in query_for_viz.lower() and ctype not in analysis["suitable_charts"]:
                            better = analysis["recommended_chart"] or "bar"
                            st.info(f"A {ctype} chart isn't ideal for this data. Showing a {better} chart instead.")
                            break

                    # Main results expander with visualization
                    wants_table = "table" in query_for_viz.lower()
                    with st.expander(f"📊 Results ({row_count} rows)", expanded=True):
                        if has_charts:
                            render_visualization(
                                df,
                                title=None,
                                key_prefix=get_unique_key("v2_viz", results),
                                show_selector=True,
                                default_expanded=wants_viz or len(df) <= 10,
                                allow_download=True
                            )
                        else:
                            st.dataframe(df, width="stretch", hide_index=True)

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

            # Follow-up suggestion buttons (shown randomly after first few messages)
            if msg.get("suggestions"):
                v2_msg_count = st.session_state.get("v2_msg_count", 0)
                rng = random.Random(message_index)
                show_suggestions = v2_msg_count <= 2 or rng.random() < 0.4
                if show_suggestions:
                    st.markdown("**You might also want to ask:**")
                    suggestion_cols = st.columns(min(len(msg["suggestions"]), 3))
                    for j, suggestion in enumerate(msg["suggestions"][:3]):
                        with suggestion_cols[j]:
                            if st.button(
                                f"💡 {suggestion}",
                                key=get_unique_key(f"v2_sug_{j}", suggestion),
                                use_container_width=True
                            ):
                                st.session_state["v2_pending_suggestion"] = suggestion
                                st.rerun()


def render_suggested_questions():
    """Shows some starter questions the user can click on to get going."""
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
            if st.button(suggestion, key=f"suggest_{i}", width="stretch"):
                return suggestion

    return None
