"""Chat page - main chat interface."""
import streamlit as st
import json
from frontend.api_client import APIClient
from frontend.components.chat_message import render_message
from frontend.components.feedback_buttons import render_feedback_buttons


def render_chat():
    """Render the chat interface."""
    st.title("Chat with Crew Assistant")

    # Initialize API client with token
    client = APIClient(st.session_state.token)

    # Display conversation history
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.messages:
            render_message(msg, client)

    # Chat input
    if prompt := st.chat_input("Ask me anything about crew policies, schedules, or data..."):
        # Add user message to display
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)

        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.write(prompt)

        # Send to backend
        with st.spinner("Thinking..."):
            result = client.send_message(prompt, st.session_state.conversation_id)

        if result.get("error"):
            st.error(f"Error: {result.get('detail', 'Unknown error')}")
        else:
            # Update conversation ID
            st.session_state.conversation_id = result.get("conversation_id")

            # Create assistant message
            assistant_msg = {
                "role": "assistant",
                "content": result.get("response", ""),
                "message_id": result.get("message_id"),
                "intent": result.get("intent"),
                "confidence": result.get("confidence"),
                "sql_query": result.get("sql_query"),
                "sql_results": result.get("sql_results"),
                "sources": result.get("sources"),
                "processing_time_ms": result.get("processing_time_ms")
            }
            st.session_state.messages.append(assistant_msg)

            # Rerun to display new message
            st.rerun()

    # Sidebar - conversation info
    with st.sidebar:
        if st.session_state.conversation_id:
            st.caption(f"Conversation ID: {st.session_state.conversation_id}")

        # Load previous conversations
        st.subheader("Recent Conversations")
        conversations = client.list_conversations(limit=10)

        if not conversations.get("error") and conversations.get("conversations"):
            for conv in conversations["conversations"]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Truncate title if too long
                    title = conv.get("title", "Untitled")[:30]
                    if len(conv.get("title", "")) > 30:
                        title += "..."
                    if st.button(title, key=f"conv_{conv['conversation_id']}", use_container_width=True):
                        load_conversation(client, conv["conversation_id"])
        else:
            st.caption("No previous conversations")


def load_conversation(client: APIClient, conversation_id: int):
    """Load a previous conversation."""
    result = client.get_history(conversation_id)

    if result.get("error"):
        st.error(f"Failed to load conversation: {result.get('detail')}")
        return

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = []

    for msg in result.get("messages", []):
        formatted_msg = {
            "role": msg["role"],
            "content": msg["content"],
            "message_id": msg.get("message_id"),
            "intent": msg.get("intent"),
            "confidence": msg.get("confidence"),
            "sql_query": msg.get("sql_generated"),
            "sources": msg.get("source_documents"),
            "processing_time_ms": msg.get("processing_time_ms")
        }
        st.session_state.messages.append(formatted_msg)

    st.rerun()
