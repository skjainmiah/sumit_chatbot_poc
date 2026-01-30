"""Chat page - main V1 chat interface with visualization support."""
import streamlit as st
from frontend.api_client import APIClient
from frontend.components.chat_message import render_message
from frontend.components.feedback_buttons import render_feedback_buttons
from frontend.components.visualization import reset_key_counts
from frontend.components.loading_facts import show_loading_with_facts


def _init_visitor_name(client: APIClient):
    """Check for visitor name on first load. Sets session state flags."""
    if "visitor_name_checked" in st.session_state:
        return
    st.session_state["visitor_name_checked"] = True
    try:
        result = client.get_visitor_name()
        if result.get("name"):
            st.session_state["visitor_name"] = result["name"]
        else:
            st.session_state["awaiting_name"] = True
    except Exception:
        # Don't block chat if visitor name lookup fails
        st.session_state["visitor_name_checked"] = True


def render_chat():
    """Main V1 chat page - displays messages, handles user input, shows conversation history."""
    st.title("Chat with Crew Assistant")
    st.caption("Ask about crew data, policies, schedules, and more")

    # Initialize API client with token
    client = APIClient(st.session_state.token)

    # Visitor name greeting
    _init_visitor_name(client)

    # Display conversation history
    chat_container = st.container()
    reset_key_counts()

    with chat_container:
        # Show greeting or name prompt as first message when conversation is empty
        if not st.session_state.messages:
            visitor_name = st.session_state.get("visitor_name")
            if visitor_name:
                with st.chat_message("assistant", avatar=None):
                    st.write(f"Welcome back, {visitor_name}!")
            elif st.session_state.get("awaiting_name"):
                with st.chat_message("assistant", avatar=None):
                    st.write("Hi! What should I call you?")

        for i, msg in enumerate(st.session_state.messages):
            # Get the user query that preceded this assistant message
            user_query = ""
            if msg.get("role") == "assistant" and i > 0:
                prev_msg = st.session_state.messages[i - 1]
                if prev_msg.get("role") == "user":
                    user_query = prev_msg.get("content", "")

            render_message(msg, client, user_query=user_query, message_index=i)

    # Handle pending suggestion clicks
    pending = st.session_state.pop("v1_pending_suggestion", None)

    # Chat input
    if prompt := (pending or st.chat_input("Ask me anything about crew policies, schedules, or data...")):
        # If awaiting visitor name, capture it instead of sending to LLM
        if st.session_state.get("awaiting_name"):
            st.session_state["visitor_name"] = prompt.strip()
            st.session_state["awaiting_name"] = False
            try:
                client.set_visitor_name(prompt.strip())
            except Exception:
                pass
            st.rerun()
            return
        # Track message count for suggestion randomization
        st.session_state["v1_msg_count"] = st.session_state.get("v1_msg_count", 0) + 1

        # Add user message to display
        user_msg = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_msg)

        # Display user message
        with chat_container:
            with st.chat_message("user", avatar=None):
                st.write(prompt)

        # Auto-scroll to show the user's question above the input bar
        st.markdown(
            "<script>window.parent.document.querySelector('section.main').scrollTo(0, 999999)</script>",
            unsafe_allow_html=True,
        )

        # Send to backend with loading animation
        loading_placeholder = st.empty()
        stop_event = show_loading_with_facts(loading_placeholder)
        try:
            result = client.send_message(prompt, st.session_state.conversation_id)
        finally:
            stop_event.set()
            loading_placeholder.empty()

        if result.get("error"):
            st.error(f"Error: {result.get('detail', 'Unknown error')}")
        else:
            # Update conversation ID
            st.session_state.conversation_id = result.get("conversation_id")

            # Create assistant message (store user_query for visualization suggestions)
            assistant_msg = {
                "role": "assistant",
                "content": result.get("response", ""),
                "message_id": result.get("message_id"),
                "intent": result.get("intent"),
                "confidence": result.get("confidence"),
                "sql_query": result.get("sql_query"),
                "sql_results": result.get("sql_results"),
                "sources": result.get("sources"),
                "suggestions": result.get("suggestions"),
                "processing_time_ms": result.get("processing_time_ms"),
                "user_query": prompt,
            }
            st.session_state.messages.append(assistant_msg)

            # Rerun to display new message
            st.rerun()

    # Sidebar - conversation info
    with st.sidebar:
        visitor_name = st.session_state.get("visitor_name")
        if visitor_name:
            st.caption(f"👤 Hi, {visitor_name}")

        st.subheader("📋 Conversation")

        if st.session_state.conversation_id:
            st.caption(f"ID: {st.session_state.conversation_id}")

        # New conversation button
        if st.button("🔄 New Conversation", width="stretch"):
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.rerun()

        st.divider()

        # Load previous conversations
        st.subheader("📚 Recent Conversations")
        conversations = client.list_conversations(limit=10)

        if not conversations.get("error") and conversations.get("conversations"):
            for conv in conversations["conversations"]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Truncate title if too long
                    title = conv.get("title", "Untitled")[:30]
                    if len(conv.get("title", "")) > 30:
                        title += "..."
                    if st.button(title, key=f"conv_{conv['conversation_id']}", width="stretch"):
                        load_conversation(client, conv["conversation_id"])
        else:
            st.caption("No previous conversations")

        st.divider()

        # Quick tips
        with st.expander("💡 Tips"):
            st.markdown("""
            **Try asking:**
            - "Show crew members by role"
            - "List flights to Dallas"
            - "Who is unawarded in January?"
            - "Compare payroll by department"

            **For charts, try:**
            - "Show a chart of crew by base"
            - "Visualize training scores"
            - "Compare leave balances"
            """)


def load_conversation(client: APIClient, conversation_id: int):
    """Fetches and loads a previous conversation from the backend into session state."""
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
