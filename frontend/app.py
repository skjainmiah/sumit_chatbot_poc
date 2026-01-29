"""Main Streamlit application entry point."""
import sys
import os

# Add project root to Python path so 'frontend' and 'backend' packages are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from frontend.config import PAGE_TITLE, PAGE_ICON

# Page configuration
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []


def main():
    """Main application router."""
    if not st.session_state.authenticated:
        from frontend.views.login import render_login
        render_login()
    else:
        # Sidebar navigation
        with st.sidebar:
            st.title(PAGE_ICON + " " + PAGE_TITLE)
            st.divider()

            # User info
            if st.session_state.user:
                st.write(f"Welcome, **{st.session_state.user.get('full_name', st.session_state.user.get('username', 'User'))}**")
                st.caption(f"Role: {st.session_state.user.get('role', 'user').title()}")

            st.divider()

            # Navigation - include both chat versions
            nav_options = ["Chat V1", "Chat V2", "Database Explorer"]
            if st.session_state.user and st.session_state.user.get("role") == "admin":
                nav_options.append("Admin Panel")

            page = st.radio("Navigation", nav_options, label_visibility="collapsed")

            st.divider()

            # New conversation button (clears both V1 and V2)
            if st.button("New Conversation", use_container_width=True):
                st.session_state.conversation_id = None
                st.session_state.messages = []
                # Also clear V2 state if exists
                if "conversation_id_v2" in st.session_state:
                    st.session_state.conversation_id_v2 = None
                if "messages_v2" in st.session_state:
                    st.session_state.messages_v2 = []
                st.rerun()

            # Logout button
            if st.button("Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.token = None
                st.session_state.user = None
                st.session_state.conversation_id = None
                st.session_state.messages = []
                st.rerun()

        # Main content
        if page == "Chat V1":
            from frontend.views.chat import render_chat
            render_chat()
        elif page == "Chat V2":
            from frontend.views.chat_v2 import render_chat_v2
            render_chat_v2()
        elif page == "Database Explorer":
            from frontend.views.db_explorer import render_db_explorer
            render_db_explorer()
        elif page == "Admin Panel":
            from frontend.views.admin import render_admin
            render_admin()


if __name__ == "__main__":
    main()
