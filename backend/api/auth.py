"""Authentication API endpoints."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from backend.auth.models import LoginRequest, TokenResponse, UserCreate, UserResponse
from backend.auth.password import hash_password, verify_password
from backend.auth.jwt_handler import create_access_token, verify_token, TokenData
from backend.db.session import get_app_db, execute_query, execute_write
from backend.config import settings

router = APIRouter()


def get_current_user(token: str) -> dict:
    """Dependency to get current user from token."""
    token_data = verify_token(token)
    if token_data is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {
        "user_id": token_data.user_id,
        "username": token_data.username,
        "role": token_data.role
    }


def require_admin(token: str) -> dict:
    """Dependency that requires admin role."""
    user = get_current_user(token)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    with get_app_db() as conn:
        cursor = conn.execute(
            "SELECT user_id, username, password_hash, role, is_active FROM users WHERE username = ?",
            (request.username,)
        )
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_dict = dict(user)
    if not user_dict["is_active"]:
        raise HTTPException(status_code=401, detail="User account is inactive")

    if not verify_password(request.password, user_dict["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Update last login
    with get_app_db() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE user_id = ?",
            (datetime.utcnow().isoformat(), user_dict["user_id"])
        )
        conn.commit()

    # Create token
    token = create_access_token({
        "sub": user_dict["username"],
        "user_id": user_dict["user_id"],
        "role": user_dict["role"]
    })

    return TokenResponse(
        access_token=token,
        user_id=user_dict["user_id"],
        username=user_dict["username"],
        role=user_dict["role"]
    )


@router.post("/register", response_model=UserResponse)
async def register(request: UserCreate, admin_token: str = None):
    """Register a new user (admin only or first user)."""
    # Check if any users exist
    users = execute_query(settings.app_db_path, "SELECT COUNT(*) as count FROM users")
    is_first_user = users[0]["count"] == 0

    # If not first user, require admin token
    if not is_first_user:
        if not admin_token:
            raise HTTPException(status_code=403, detail="Admin token required")
        token_data = verify_token(admin_token)
        if not token_data or token_data.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

    # Check if username or email already exists
    existing = execute_query(
        settings.app_db_path,
        "SELECT user_id FROM users WHERE username = ? OR email = ?",
        (request.username, request.email)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    # Create user
    password_hash = hash_password(request.password)
    role = "admin" if is_first_user else request.role

    user_id = execute_write(
        settings.app_db_path,
        """INSERT INTO users (username, email, password_hash, full_name, role)
           VALUES (?, ?, ?, ?, ?)""",
        (request.username, request.email, password_hash, request.full_name, role)
    )

    return UserResponse(
        user_id=user_id,
        username=request.username,
        email=request.email,
        full_name=request.full_name,
        role=role,
        is_active=True
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(token: str):
    """Get current user information."""
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    users = execute_query(
        settings.app_db_path,
        "SELECT user_id, username, email, full_name, role, is_active FROM users WHERE user_id = ?",
        (token_data.user_id,)
    )
    if not users:
        raise HTTPException(status_code=404, detail="User not found")

    user = users[0]
    return UserResponse(**user)


@router.post("/refresh")
async def refresh_token(token: str):
    """Refresh an existing token."""
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")

    new_token = create_access_token({
        "sub": token_data.username,
        "user_id": token_data.user_id,
        "role": token_data.role
    })

    return {"access_token": new_token, "token_type": "bearer"}


# ==========================================
# Visitor name (IP-based greeting)
# ==========================================

class VisitorNameRequest(BaseModel):
    name: str


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, checking X-Forwarded-For header first."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


@router.get("/visitor-name")
async def get_visitor_name(request: Request):
    """Look up visitor's preferred name by IP address."""
    ip = _get_client_ip(request)
    rows = execute_query(
        settings.app_db_path,
        "SELECT preferred_name FROM visitor_names WHERE ip_address = ?",
        (ip,)
    )
    if rows:
        return {"name": rows[0]["preferred_name"]}
    return {"name": None}


@router.post("/visitor-name")
async def set_visitor_name(request: Request, body: VisitorNameRequest):
    """Store or update visitor's preferred name by IP address."""
    ip = _get_client_ip(request)
    now = datetime.utcnow().isoformat()
    with get_app_db() as conn:
        conn.execute(
            """INSERT INTO visitor_names (ip_address, preferred_name, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ip_address) DO UPDATE SET preferred_name = ?, updated_at = ?""",
            (ip, body.name, now, now, body.name, now)
        )
        conn.commit()
    return {"success": True, "name": body.name}
