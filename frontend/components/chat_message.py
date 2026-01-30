"""Renders individual chat messages with intent badges, SQL results, and follow-up suggestions."""
import random
import streamlit as st
from frontend.components.sql_display import render_sql_results
from frontend.components.source_display import render_sources
from frontend.components.feedback_buttons import render_feedback_buttons
from frontend.components.visualization import get_unique_key


def render_message(msg: dict, client=None, user_query: str = "", message_index: int = 0):
    """Shows a single chat message with intent badge, SQL results, suggestions, and feedback."""
    role = msg.get("role", "user")

    with st.chat_message(role, avatar=None):
        # Main content
        st.write(msg.get("content", ""))

        # For assistant messages, show additional info
        if role == "assistant":
            # Intent badge
            intent = msg.get("intent")
            confidence = msg.get("confidence")
            if intent:
                intent_colors = {
                    "DATA": "blue",
                    "GENERAL": "gray",
                    "CLARIFICATION": "orange"
                }
                color = intent_colors.get(intent, "gray")
                conf_str = f" | Confidence: {confidence:.0%}" if confidence else ""
                st.caption(f"Intent: :{color}[{intent}]{conf_str}")

            # SQL results with visualization
            if msg.get("sql_query") or msg.get("sql_results"):
                # Get original query for better chart suggestions
                query_text = user_query or msg.get("user_query", "")
                render_sql_results(
                    msg.get("sql_query"),
                    msg.get("sql_results"),
                    query_text=query_text
                )

            # RAG sources
            if msg.get("sources"):
                render_sources(msg.get("sources"))

            # Processing time
            if msg.get("processing_time_ms"):
                time_ms = msg.get("processing_time_ms")
                if time_ms < 2000:
                    st.caption(f"Response time: :green[{time_ms}ms]")
                elif time_ms < 5000:
                    st.caption(f"Response time: :orange[{time_ms}ms]")
                else:
                    st.caption(f"Response time: :red[{time_ms}ms]")

            # Follow-up suggestion buttons (shown randomly after first few messages)
            if msg.get("suggestions"):
                v1_msg_count = st.session_state.get("v1_msg_count", 0)
                rng = random.Random(message_index)
                show_suggestions = v1_msg_count <= 2 or rng.random() < 0.4
                if show_suggestions:
                    st.markdown("**You might also want to ask:**")
                    suggestion_cols = st.columns(min(len(msg["suggestions"]), 3))
                    for j, suggestion in enumerate(msg["suggestions"][:3]):
                        with suggestion_cols[j]:
                            if st.button(
                                f"💡 {suggestion}",
                                key=get_unique_key(f"v1_sug_{j}", suggestion),
                                use_container_width=True
                            ):
                                st.session_state["v1_pending_suggestion"] = suggestion
                                st.rerun()

            # Feedback buttons
            if msg.get("message_id") and client:
                render_feedback_buttons(msg.get("message_id"), client)
