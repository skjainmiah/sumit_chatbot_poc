"""Seed admin user for the application."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.session import execute_write, execute_query
from backend.auth.password import hash_password
from backend.config import settings


def seed_admin_user():
    """Create default admin user if not exists."""
    print("Seeding admin user...")

    # Check if admin already exists
    existing = execute_query(
        settings.app_db_path,
        "SELECT user_id FROM users WHERE username = ?",
        ("admin",)
    )

    if existing:
        print("Admin user already exists.")
        return

    # Create admin user
    hashed_pw = hash_password("admin123")  # Default password - CHANGE IN PRODUCTION

    execute_write(
        settings.app_db_path,
        """INSERT INTO users (username, email, password_hash, full_name, role, is_active)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("admin", "admin@aa.com", hashed_pw, "System Administrator", "admin", True)
    )

    print("Admin user created successfully!")
    print("  Username: admin")
    print("  Password: admin123")
    print("  ** CHANGE PASSWORD IN PRODUCTION **")


def seed_test_user():
    """Create test regular user if not exists."""
    print("Seeding test user...")

    existing = execute_query(
        settings.app_db_path,
        "SELECT user_id FROM users WHERE username = ?",
        ("testuser",)
    )

    if existing:
        print("Test user already exists.")
        return

    hashed_pw = hash_password("test123")

    execute_write(
        settings.app_db_path,
        """INSERT INTO users (username, email, password_hash, full_name, role, is_active)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("testuser", "testuser@aa.com", hashed_pw, "Test User", "user", True)
    )

    print("Test user created successfully!")
    print("  Username: testuser")
    print("  Password: test123")


if __name__ == "__main__":
    seed_admin_user()
    seed_test_user()
