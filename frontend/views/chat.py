"""Chat page - main V1 chat interface with visualization support."""
import streamlit as st
from frontend.api_client import APIClient
from frontend.components.chat_message import render_message
from frontend.components.feedback_buttons import render_feedback_buttons
from frontend.components.visualization import reset_key_counts
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

    # Too many words or contains '?' → probably not a name
    words = text.split()
    if len(words) > 3 or "?" in text:
        return None

    if words:
        name = words[0]
        return name[0].upper() + name[1:] if len(name) > 1 else name.upper()
    return None


def _is_name_change_request(text: str):
    """Return (True, new_name) if the user wants to change their name, else (False, None).

    Uses keyword detection so phrases like "change my name to X",
    "I want my name changed to X", "please call me Y" all work regardless
    of exact word order.
    """
    import re
    lower = text.strip().lower()

    # --- Prefix-based patterns (highest confidence) ---
    prefix_patterns = [
        "change my name to ", "rename me to ",
        "please call me ", "update my name to ",
        "i want to be called ", "call me ",
        "my name is actually ", "actually my name is ",
        "actually i'm ", "actually i am ",
    ]
    for pattern in prefix_patterns:
        if lower.startswith(pattern):
            raw = text.strip()[len(pattern):]
            name = _extract_name(raw)
            if name:
                return True, name

    # --- Keyword-based detection (catches "change my name" anywhere) ---
    # Look for "change" + "name" together, then extract the name after "to"
    if re.search(r'\bchange\b.*\bname\b', lower) or re.search(r'\bname\b.*\bchange\b', lower):
        # Try to find "to <name>" at the end
        m = re.search(r'\bto\s+(.+)$', lower)
        if m:
            name = _extract_name(m.group(1))
            if name:
                return True, name

    # "call me <name>" anywhere in the sentence
    m = re.search(r'\bcall\s+me\s+(.+?)(?:\s+from\s+now|\s+instead|\s*[.!?]?\s*$)', lower)
    if m:
        name = _extract_name(m.group(1))
        if name:
            return True, name

    return False, None


def _init_visitor_name(client: APIClient):
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
        # Welcome back for returning users (empty conversation only)
        if not st.session_state.messages:
            visitor_name = st.session_state.get("visitor_name")
            if visitor_name:
                with st.chat_message("assistant", avatar=None):
                    st.write(f"Welcome back, {visitor_name}!")

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

        # --- 1. Name-change / name-set request ---
        is_change, new_name = _is_name_change_request(prompt)
        if is_change and new_name:
            old_name = st.session_state.get("visitor_name")
            st.session_state["visitor_name"] = new_name
            st.session_state.pop("needs_name", None)
            st.session_state.pop("awaiting_name", None)
            try:
                client.set_visitor_name(new_name)
            except Exception:
                pass
            st.session_state.messages.append({"role": "user", "content": prompt})
            if old_name:
                reply = f"Sure! I'll call you {new_name} from now on."
            else:
                reply = f"Nice to meet you, {new_name}! How can I help you today?"
            st.session_state.messages.append({"role": "assistant", "content": reply})
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
                st.session_state.messages.append({"role": "user", "content": prompt})
                if st.session_state.pop("greeting_name_ask", False):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Hello, {name}! How can I help you today?",
                    })
                else:
                    st.session_state.messages.append({
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
        has_user_msgs = any(m.get("role") == "user" for m in st.session_state.messages)
        if st.session_state.get("needs_name") and not has_user_msgs:
            if _is_greeting(prompt):
                # Pure greeting → ask for name instead of sending to LLM
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Hello! Can I know your good name?",
                })
                st.session_state["awaiting_name"] = True
                st.session_state["greeting_name_ask"] = True
                st.rerun()
                return
            else:
                # It's a real question — flag so we ask for name after the LLM reply
                st.session_state["ask_name_after_response"] = True

        # --- Normal message flow ---
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
        stop_event, min_shown_event = show_loading_with_facts(loading_placeholder)
        try:
            result = client.send_message(prompt, st.session_state.conversation_id)
        finally:
            stop_event.set()
            # Wait until at least 2 facts have been shown (or no facts were shown)
            min_shown_event.wait(timeout=15)
            loading_placeholder.empty()

        if result.get("error"):
            st.error(f"Error: {result.get('detail', 'Unknown error')}")
        else:
            # Update conversation ID
            st.session_state.conversation_id = result.get("conversation_id")

            content = result.get("response", "")

            # Append name question if this was the first question and we need a name
            if st.session_state.pop("ask_name_after_response", False):
                content += "\n\nBy the way, can I know your good name?"
                st.session_state["awaiting_name"] = True

            # Create assistant message (store user_query for visualization suggestions)
            assistant_msg = {
                "role": "assistant",
                "content": content,
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
