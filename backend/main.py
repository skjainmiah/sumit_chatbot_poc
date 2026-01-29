"""FastAPI application entry point."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.api.router import api_router
from backend.config import settings

# Import v2 API (PostgreSQL with full schema)
try:
    from backend.api import chat_v2
    HAS_V2_API = True
except ImportError as e:
    print(f"Warning: v2 API not available: {e}")
    HAS_V2_API = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("Starting Crew Chatbot API...")
    print(f"LLM Model: {settings.LLM_MODEL}")

    # Check which mode we're running
    use_postgres = os.getenv("USE_POSTGRES", "false").lower() == "true"
    if use_postgres and HAS_V2_API:
        print("Mode: PostgreSQL (v2 API)")
        print(f"PostgreSQL: {os.getenv('PGHOST', 'localhost')}:{os.getenv('PGPORT', '5432')}")
    else:
        print("Mode: SQLite (v1 API)")
        print(f"Database Dir: {settings.DATABASE_DIR}")

    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="American Airlines Crew Chatbot API",
    description="AI-powered chatbot for airline crew management with RAG and Text-to-SQL",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Include v2 API routes (PostgreSQL with full schema)
if HAS_V2_API:
    app.include_router(chat_v2.router, prefix="/api/v2/chat", tags=["Chat V2 (PostgreSQL)"])


@app.get("/")
async def root():
    """Root endpoint."""
    use_postgres = os.getenv("USE_POSTGRES", "false").lower() == "true"
    return {
        "name": "Crew Chatbot API",
        "version": "2.0.0",
        "status": "running",
        "mode": "postgresql" if use_postgres else "sqlite",
        "endpoints": {
            "v1": "/api/chat (SQLite)",
            "v2": "/api/v2/chat (PostgreSQL)" if HAS_V2_API else "not available"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
