"""Chat message component."""
import streamlit as st
from frontend.components.sql_display import render_sql_results
from frontend.components.source_display import render_sources
from frontend.components.feedback_buttons import render_feedback_buttons


def render_message(msg: dict, client=None):
    """Render a single chat message."""
    role = msg.get("role", "user")

    with st.chat_message(role):
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
                st.caption(f"Intent: :{color}[{intent}] | Confidence: {confidence:.0%}" if confidence else f"Intent: :{color}[{intent}]")

            # SQL results
            if msg.get("sql_query") or msg.get("sql_results"):
                render_sql_results(msg.get("sql_query"), msg.get("sql_results"))

            # RAG sources
            if msg.get("sources"):
                render_sources(msg.get("sources"))

            # Processing time
            if msg.get("processing_time_ms"):
                st.caption(f"Response time: {msg.get('processing_time_ms')}ms")

            # Feedback buttons
            if msg.get("message_id") and client:
                render_feedback_buttons(msg.get("message_id"), client)
