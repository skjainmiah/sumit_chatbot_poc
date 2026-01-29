"""Admin API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from backend.auth.jwt_handler import verify_token
from backend.auth.models import UserResponse, UserUpdate
from backend.auth.password import hash_password
from backend.db.session import execute_query, execute_write
from backend.config import settings

router = APIRouter()


def require_admin(token: str):
    """Verify admin role."""
    token_data = verify_token(token)
    if not token_data or token_data.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return token_data


@router.get("/users", response_model=List[UserResponse])
async def list_users(token: str):
    """List all users (admin only)."""
    require_admin(token)
    users = execute_query(
        settings.app_db_path,
        "SELECT user_id, username, email, full_name, role, is_active FROM users ORDER BY user_id"
    )
    return [UserResponse(**u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, token: str):
    """Get a specific user (admin only)."""
    require_admin(token)
    users = execute_query(
        settings.app_db_path,
        "SELECT user_id, username, email, full_name, role, is_active FROM users WHERE user_id = ?",
        (user_id,)
    )
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**users[0])


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, update: UserUpdate, token: str):
    """Update a user (admin only)."""
    require_admin(token)

    # Build update query dynamically
    updates = []
    params = []
    if update.email is not None:
        updates.append("email = ?")
        params.append(update.email)
    if update.full_name is not None:
        updates.append("full_name = ?")
        params.append(update.full_name)
    if update.role is not None:
        updates.append("role = ?")
        params.append(update.role)
    if update.is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if update.is_active else 0)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?"
    execute_write(settings.app_db_path, query, tuple(params))

    return await get_user(user_id, token)


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, token: str):
    """Delete a user (admin only)."""
    admin = require_admin(token)
    if admin.user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    execute_write(settings.app_db_path, "DELETE FROM users WHERE user_id = ?", (user_id,))
    return {"message": "User deleted"}


@router.get("/feedback")
async def list_feedback(
    token: str,
    rating: Optional[str] = None,
    limit: int = Query(default=50, le=200)
):
    """List feedback (admin only)."""
    require_admin(token)

    query = """
        SELECT f.feedback_id, f.message_id, f.user_id, f.rating, f.comment, f.created_at,
               m.content as message_content, m.intent, u.username
        FROM feedback f
        JOIN messages m ON f.message_id = m.message_id
        JOIN users u ON f.user_id = u.user_id
    """
    params = []
    if rating:
        query += " WHERE f.rating = ?"
        params.append(rating)
    query += f" ORDER BY f.created_at DESC LIMIT {limit}"

    return execute_query(settings.app_db_path, query, tuple(params))


@router.get("/stats")
async def get_stats(token: str):
    """Get usage statistics (admin only)."""
    require_admin(token)

    stats = {}

    # User count
    result = execute_query(settings.app_db_path, "SELECT COUNT(*) as count FROM users")
    stats["total_users"] = result[0]["count"]

    # Active conversations
    result = execute_query(
        settings.app_db_path,
        "SELECT COUNT(*) as count FROM conversations WHERE is_active = 1"
    )
    stats["active_conversations"] = result[0]["count"]

    # Total messages
    result = execute_query(settings.app_db_path, "SELECT COUNT(*) as count FROM messages")
    stats["total_messages"] = result[0]["count"]

    # Messages by intent
    result = execute_query(
        settings.app_db_path,
        "SELECT intent, COUNT(*) as count FROM messages WHERE intent IS NOT NULL GROUP BY intent"
    )
    stats["messages_by_intent"] = {r["intent"]: r["count"] for r in result}

    # Feedback stats
    result = execute_query(
        settings.app_db_path,
        "SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating"
    )
    stats["feedback"] = {r["rating"]: r["count"] for r in result}

    return stats
