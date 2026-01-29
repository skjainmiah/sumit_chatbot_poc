"""Application configuration loaded from environment variables."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Force .env file to override system environment variables
load_dotenv(override=True)

# Calculate base directory (project root = parent of backend/)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Quasar/Coforge LLM API (REST-based, no OpenAI SDK)
    # Chat completions (v2 primary, v3 fallback)
    LLM_CHAT_URL: str = ""
    LLM_CHAT_URL_V3: str = ""
    # Embeddings (v2 primary, v3 fallback)
    LLM_EMBEDDING_URL: str = ""
    LLM_EMBEDDING_URL_V3: str = ""
    # Shared API key
    LLM_API_KEY: str = ""
    # Models
    LLM_MODEL: str = "gpt-5-2"
    LLM_FAST_MODEL: str = "gpt-5-2"
    EMBEDDING_MODEL: str = "text-embeddings"
    EMBEDDING_DIMENSIONS: int = 746
    # Network
    LLM_VERIFY_SSL: bool = False
    LLM_PROXY: str = ""

    # JWT
    JWT_SECRET: str = "change-this-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60

    # App
    INTENT_CONFIDENCE_THRESHOLD: float = 0.7
    SQL_MAX_RETRIES: int = 3
    SQL_TIMEOUT_SECONDS: int = 10
    SCHEMA_TOP_K: int = 8

    # Admin defaults
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    DEFAULT_ADMIN_EMAIL: str = "admin@americanairlines.com"

    # Database file names
    CREW_MANAGEMENT_DB: str = "crew_management.db"
    FLIGHT_OPERATIONS_DB: str = "flight_operations.db"
    HR_PAYROLL_DB: str = "hr_payroll.db"
    COMPLIANCE_TRAINING_DB: str = "compliance_training.db"
    APP_DB: str = "app.db"

    # Paths - computed as properties to always be relative to BASE_DIR
    @property
    def DATABASE_DIR(self) -> str:
        """Database directory - always relative to project root."""
        return str(BASE_DIR / "data" / "databases")

    @property
    def FAISS_INDEX_DIR(self) -> str:
        """FAISS index directory - always relative to project root."""
        return str(BASE_DIR / "data" / "faiss_indexes")

    @property
    def POLICY_DOCS_DIR(self) -> str:
        """Policy documents directory - always relative to project root."""
        return str(BASE_DIR / "data" / "policy_documents")

    @property
    def crew_db_path(self) -> str:
        return os.path.join(self.DATABASE_DIR, self.CREW_MANAGEMENT_DB)

    @property
    def flight_db_path(self) -> str:
        return os.path.join(self.DATABASE_DIR, self.FLIGHT_OPERATIONS_DB)

    @property
    def hr_db_path(self) -> str:
        return os.path.join(self.DATABASE_DIR, self.HR_PAYROLL_DB)

    @property
    def compliance_db_path(self) -> str:
        return os.path.join(self.DATABASE_DIR, self.COMPLIANCE_TRAINING_DB)

    @property
    def app_db_path(self) -> str:
        return os.path.join(self.DATABASE_DIR, self.APP_DB)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from .env (like old path settings)


settings = Settings()
