"""Feedback buttons component."""
import streamlit as st
from typing import Optional


def render_feedback_buttons(message_id: int, client):
    """Render thumbs up/down feedback buttons for a message."""
    # Create unique key for this message's feedback state
    feedback_key = f"feedback_{message_id}"

    # Check if feedback already submitted
    if feedback_key in st.session_state:
        rating = st.session_state[feedback_key]
        if rating == "thumbs_up":
            st.caption("Thanks for your feedback!")
        elif rating == "thumbs_down":
            st.caption("Thanks for your feedback!")
        return

    # Render buttons with emoji labels
    col1, col2, col3 = st.columns([1, 1, 8])

    with col1:
        if st.button("👍", key=f"thumbs_up_{message_id}", help="Good response"):
            submit_feedback(client, message_id, "thumbs_up", feedback_key)
            st.rerun()

    with col2:
        if st.button("👎", key=f"thumbs_down_{message_id}", help="Poor response"):
            submit_feedback(client, message_id, "thumbs_down", feedback_key)
            st.rerun()


def submit_feedback(client, message_id: int, rating: str, feedback_key: str, comment: str = None):
    """Submit feedback to the backend."""
    result = client.submit_feedback(message_id, rating, comment)

    if result.get("error"):
        st.error(f"Failed to submit feedback: {result.get('detail')}")
    else:
        st.session_state[feedback_key] = rating
