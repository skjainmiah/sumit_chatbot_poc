"""API client for communicating with the backend."""
import httpx
from typing import Optional, Dict, Any
from frontend.config import API_BASE


class APIClient:
    """HTTP client for backend API calls."""

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.timeout = 120.0  # 2 minutes for LLM calls

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        return headers

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the backend."""
        url = f"{API_BASE}{endpoint}"
        if self.token:
            # Add token as query param (simplified auth for MVP)
            if "params" not in kwargs:
                kwargs["params"] = {}
            kwargs["params"]["token"] = self.token

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, headers=self._get_headers(), **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = str(e)
            return {"error": True, "detail": error_detail, "status_code": e.response.status_code}
        except httpx.RequestError as e:
            return {"error": True, "detail": f"Connection error: {str(e)}"}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login and get JWT token."""
        return self._make_request(
            "POST",
            "/auth/login",
            json={"username": username, "password": password}
        )

    def register(self, username: str, email: str, password: str, full_name: str = None) -> Dict[str, Any]:
        """Register a new user."""
        return self._make_request(
            "POST",
            "/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
                "full_name": full_name
            }
        )

    def get_current_user(self) -> Dict[str, Any]:
        """Get current user info."""
        return self._make_request("GET", "/auth/me")

    def get_visitor_name(self) -> Dict[str, Any]:
        """Look up visitor's preferred name by IP."""
        return self._make_request("GET", "/auth/visitor-name")

    def set_visitor_name(self, name: str) -> Dict[str, Any]:
        """Store visitor's preferred name."""
        return self._make_request("POST", "/auth/visitor-name", json={"name": name})

    def send_message(self, message: str, conversation_id: Optional[int] = None) -> Dict[str, Any]:
        """Send a chat message."""
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return self._make_request("POST", "/chat/message", json=payload)

    def get_history(self, conversation_id: int, limit: int = 50) -> Dict[str, Any]:
        """Get conversation history."""
        return self._make_request(
            "GET",
            f"/chat/history/{conversation_id}",
            params={"limit": limit}
        )

    def list_conversations(self, limit: int = 20) -> Dict[str, Any]:
        """List user's conversations."""
        return self._make_request("GET", "/chat/conversations", params={"limit": limit})

    def new_conversation(self) -> Dict[str, Any]:
        """Start a new conversation."""
        return self._make_request("POST", "/chat/new")

    def submit_feedback(self, message_id: int, rating: str, comment: str = None) -> Dict[str, Any]:
        """Submit feedback for a message."""
        return self._make_request(
            "POST",
            "/chat/feedback",
            json={"message_id": message_id, "rating": rating, "comment": comment}
        )

    def health_check(self) -> Dict[str, Any]:
        """Check backend health."""
        return self._make_request("GET", "/health")

    # ==========================================
    # V2 API (PostgreSQL with Full Schema)
    # ==========================================

    def send_message_v2(self, message: str, conversation_id: str = None, context: str = None) -> Dict[str, Any]:
        """Send a chat message using V2 API (PostgreSQL)."""
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if context:
            payload["context"] = context
        return self._make_request("POST", "/v2/chat/message", json=payload)

    def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information (V2)."""
        return self._make_request("GET", "/v2/chat/schema/info")

    def get_schema_tables(self, database: str = None) -> Dict[str, Any]:
        """Get list of tables (V2)."""
        params = {}
        if database:
            params["database"] = database
        return self._make_request("GET", "/v2/chat/schema/tables", params=params)

    def reload_schema(self) -> Dict[str, Any]:
        """Reload schema from file (V2)."""
        return self._make_request("POST", "/v2/chat/schema/reload")

    def health_check_v2(self) -> Dict[str, Any]:
        """Check V2 API health."""
        return self._make_request("GET", "/v2/chat/health")

    # Admin endpoints
    def list_users(self) -> Dict[str, Any]:
        """List all users (admin only)."""
        return self._make_request("GET", "/admin/users")

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics (admin only)."""
        return self._make_request("GET", "/admin/stats")

    def list_feedback(self, rating: str = None, limit: int = 50) -> Dict[str, Any]:
        """List feedback (admin only)."""
        params = {"limit": limit}
        if rating:
            params["rating"] = rating
        return self._make_request("GET", "/admin/feedback", params=params)

    # ==========================================
    # Database Management API
    # ==========================================

    def upload_sql_file(self, file, auto_visible: bool = True) -> Dict[str, Any]:
        """Upload a SQL dump file to create a new database."""
        import httpx

        url = f"{API_BASE}/database/upload"
        params = {"auto_visible": auto_visible}
        if self.token:
            params["token"] = self.token

        try:
            with httpx.Client(timeout=300.0) as client:  # 5 min timeout for large files
                files = {"file": (file.name, file.getvalue(), "application/sql")}
                response = client.post(url, files=files, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = str(e)
            return {"error": True, "detail": error_detail}
        except httpx.RequestError as e:
            return {"error": True, "detail": f"Connection error: {str(e)}"}

    def upload_csv_files(self, files, db_name: str, is_new_db: bool = True, auto_visible: bool = True) -> Dict[str, Any]:
        """Upload CSV/Excel files to create tables in a database.

        Args:
            files: List of Streamlit UploadedFile objects
            db_name: Target database name
            is_new_db: True to create new DB, False to add to existing
            auto_visible: Make database visible after upload
        """
        import httpx

        url = f"{API_BASE}/database/upload-csv"
        params = {}
        if self.token:
            params["token"] = self.token

        try:
            multipart_files = [
                ("files", (f.name, f.getvalue(), "application/octet-stream"))
                for f in files
            ]
            data = {
                "db_name": db_name,
                "is_new_db": str(is_new_db).lower(),
                "auto_visible": str(auto_visible).lower(),
            }
            with httpx.Client(timeout=300.0) as client:
                response = client.post(url, files=multipart_files, data=data, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json().get("detail", str(e))
            except Exception:
                error_detail = str(e)
            return {"error": True, "detail": error_detail}
        except httpx.RequestError as e:
            return {"error": True, "detail": f"Connection error: {str(e)}"}

    def list_databases(self, include_hidden: bool = False) -> Dict[str, Any]:
        """List all registered databases."""
        return self._make_request(
            "GET",
            "/database/list",
            params={"include_hidden": include_hidden}
        )

    def set_database_visibility(self, db_name: str, is_visible: bool) -> Dict[str, Any]:
        """Set database visibility for chat queries."""
        return self._make_request(
            "PUT",
            f"/database/{db_name}/visibility",
            json={"is_visible": is_visible}
        )

    def delete_database(self, db_name: str) -> Dict[str, Any]:
        """Delete an uploaded database."""
        return self._make_request("DELETE", f"/database/{db_name}")

    def get_upload_history(self, limit: int = 50) -> list:
        """Get upload history."""
        result = self._make_request(
            "GET",
            "/database/upload-history",
            params={"limit": limit}
        )
        if isinstance(result, dict) and result.get("error"):
            return result
        return result if isinstance(result, list) else []

    def get_database_info(self, db_name: str) -> Dict[str, Any]:
        """Get information about a specific database."""
        return self._make_request("GET", f"/database/{db_name}/info")

    def get_column_descriptions(self, db_name: str) -> Dict[str, Any]:
        """Get column descriptions for all tables in a database."""
        return self._make_request("GET", f"/database/{db_name}/column-descriptions")

    def update_column_descriptions(self, db_name: str, descriptions: Dict) -> Dict[str, Any]:
        """Update column descriptions for a database."""
        return self._make_request(
            "PUT",
            f"/database/{db_name}/column-descriptions",
            json={"descriptions": descriptions}
        )

    # ---- PII Settings ----

    def get_pii_settings(self) -> Dict[str, Any]:
        """Get current PII masking settings."""
        return self._make_request("GET", "/database/settings/pii")

    def update_pii_settings(self, enabled: bool, log_enabled: bool, patterns: Dict[str, bool]) -> Dict[str, Any]:
        """Update PII masking settings."""
        return self._make_request(
            "PUT",
            "/database/settings/pii",
            json={"enabled": enabled, "log_enabled": log_enabled, "patterns": patterns}
        )

    # ---- Column-Level PII Masking ----

    def get_column_masks(self) -> Dict[str, Any]:
        """Get column-level PII mask settings."""
        return self._make_request("GET", "/database/settings/pii/columns")

    def update_column_masks(self, masks: list) -> Dict[str, Any]:
        """Update column-level PII mask settings."""
        return self._make_request(
            "PUT",
            "/database/settings/pii/columns",
            json={"masks": masks}
        )
