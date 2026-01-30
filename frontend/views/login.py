"""Login page for user authentication."""
import streamlit as st
from frontend.api_client import APIClient
from frontend.config import PAGE_TITLE, PAGE_ICON


def render_login():
    """Render the login page."""
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 2rem 0;">
                <h1>{PAGE_ICON} {PAGE_TITLE}</h1>
                <p style="color: gray;">Your AI-powered crew assistant</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Login/Register tabs
        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            render_login_form()

        with tab2:
            render_register_form()


def render_login_form():
    """Render the login form."""
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", width="stretch")

        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
                return

            client = APIClient()
            result = client.login(username, password)

            if result.get("error"):
                st.error(result.get("detail", "Login failed"))
            else:
                st.session_state.authenticated = True
                st.session_state.token = result.get("access_token")
                st.session_state.user = result.get("user")
                st.success("Login successful!")
                st.rerun()


def render_register_form():
    """Render the registration form."""
    with st.form("register_form"):
        username = st.text_input("Username", placeholder="Choose a username", key="reg_username")
        email = st.text_input("Email", placeholder="Enter your email", key="reg_email")
        full_name = st.text_input("Full Name", placeholder="Enter your full name", key="reg_fullname")
        password = st.text_input("Password", type="password", placeholder="Choose a password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password", key="reg_confirm")
        submit = st.form_submit_button("Register", width="stretch")

        if submit:
            if not all([username, email, password, confirm_password]):
                st.error("Please fill in all required fields")
                return

            if password != confirm_password:
                st.error("Passwords do not match")
                return

            if len(password) < 6:
                st.error("Password must be at least 6 characters")
                return

            client = APIClient()
            result = client.register(username, email, password, full_name)

            if result.get("error"):
                st.error(result.get("detail", "Registration failed"))
            else:
                st.success("Registration successful! Please login.")
