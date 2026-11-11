from app.core.config import Settings


def test_settings_default_values():
    settings = Settings()
    assert settings.APP_NAME == "LOGIPULSE Backend API"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.ENVIRONMENT == "development"
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000
    assert settings.DATABASE_URL == "sqlite:///./logipulse.db"
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert "http://localhost:5173" in settings.ALLOWED_ORIGINS
    assert "http://localhost:3000" in settings.ALLOWED_ORIGINS
    assert settings.LOG_LEVEL == "INFO"
    assert settings.SIMULATION_SEED == 42


def test_settings_parses_comma_separated_allowed_origins():
    custom_origins = "http://client.local:3000, http://dashboard.local:5173,https://staging.logipulse.io"
    settings = Settings(ALLOWED_ORIGINS=custom_origins)
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert len(settings.ALLOWED_ORIGINS) == 3
    assert settings.ALLOWED_ORIGINS == [
        "http://client.local:3000",
        "http://dashboard.local:5173",
        "https://staging.logipulse.io",
    ]


def test_settings_preserves_list_allowed_origins():
    list_origins = ["http://example1.com", "http://example2.com"]
    settings = Settings(ALLOWED_ORIGINS=list_origins)
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert settings.ALLOWED_ORIGINS == list_origins

