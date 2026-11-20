from typing import List, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "LOGIPULSE Backend API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./logipulse.db"
    ALLOWED_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    LOG_LEVEL: str = "INFO"
    SIMULATION_SEED: int = 42

    # JWT Authentication & Security
    # WARNING: JWT_SECRET_KEY must be overridden with a strong secret in production!
    JWT_SECRET_KEY: str = "dev-insecure-jwt-secret-key-change-in-production-logipulse-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Demo Seeding Password (development only)
    DEMO_PASSWORD: str = "LogiPulse#2026"

    # API Rate Limiting Configuration (requests per minute)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_AI_PER_MINUTE: int = 20
    RATE_LIMIT_REPORT_PER_MINUTE: int = 15

    # Database Connection Pool Configuration
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Observability & Metrics
    METRICS_ENABLED: bool = True

    # Multi-Agent AI Configuration (Stage 10)
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    AI_PRIMARY_PROVIDER: str = "gemini"
    AI_FALLBACK_PROVIDER: str = "groq"
    AI_TIMEOUT_SECONDS: float = 30.0
    AI_MAX_RETRIES: int = 2
    AI_MAX_ORCHESTRATION_DEPTH: int = 5
    AI_MAX_CONCURRENCY: int = 4

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """
        Enforce strict production security checks when running in production mode.
        Fails fast at startup if critical secrets or configs are insecure.
        """
        env = (self.ENVIRONMENT or "").strip().lower()
        if env == "production":
            insecure_defaults = [
                "dev-insecure-jwt-secret-key-change-in-production-logipulse-2026",
                "secret",
                "changeme",
                "password",
            ]
            if self.JWT_SECRET_KEY in insecure_defaults or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "CRITICAL PRODUCTION SECURITY ERROR: JWT_SECRET_KEY must be a cryptographically "
                    "secure string of at least 32 characters in production."
                )

            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(
                    "CRITICAL PRODUCTION SECURITY ERROR: Production environment cannot use SQLite. "
                    "Configure a production-grade PostgreSQL connection string."
                )

            # Ensure origins don't allow open wildcard in production
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError(
                    "CRITICAL PRODUCTION SECURITY ERROR: Wildcard '*' is strictly forbidden in "
                    "ALLOWED_ORIGINS in production mode."
                )
        return self


settings = Settings()

