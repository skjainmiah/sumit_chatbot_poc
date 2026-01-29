"""FastAPI application entry point."""
import os
import uuid
import time
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from backend.api.router import api_router
from backend.config import settings

# ============================================================
# Logging setup
# ============================================================
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("chatbot")

# Import v2 API (PostgreSQL with full schema)
try:
    from backend.api import chat_v2
    HAS_V2_API = True
except ImportError as e:
    logger.warning(f"v2 API not available: {e}")
    HAS_V2_API = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Crew Chatbot API...")
    logger.info(f"LLM Model: {settings.LLM_MODEL}")

    # Check which mode we're running
    use_postgres = os.getenv("USE_POSTGRES", "false").lower() == "true"
    if use_postgres and HAS_V2_API:
        logger.info("Mode: PostgreSQL (v2 API)")
        logger.info(f"PostgreSQL: {os.getenv('PGHOST', 'localhost')}:{os.getenv('PGPORT', '5432')}")
    else:
        logger.info("Mode: SQLite (v1 API)")
        logger.info(f"Database Dir: {settings.DATABASE_DIR}")

    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="American Airlines Crew Chatbot API",
    description="AI-powered chatbot for airline crew management with RAG and Text-to-SQL",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================
# Global exception handler
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_id = str(uuid.uuid4())[:8]
    logger.error(f"Unhandled exception [{error_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "response": "Something went wrong. Please try again.",
            "error_id": error_id,
        },
    )


# ============================================================
# Request logging middleware
# ============================================================
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)")
    return response


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
