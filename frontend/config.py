"""Frontend configuration."""
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_BASE = f"{BACKEND_URL}/api"

PAGE_TITLE = "American Airlines Crew Assistant"
PAGE_ICON = "✈️"
