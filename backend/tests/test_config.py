from app.config import Settings


def test_settings_cors_string_parsing() -> None:
    """Verify that comma-separated CORS origins string parses into a list."""
    settings = Settings(
        CORS_ORIGINS="http://localhost:3000,http://example.com",
    )
    assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://example.com"]


def test_settings_defaults() -> None:
    """Verify default settings values for optimizer and environment."""
    settings = Settings()
    assert settings.SOLVER_TIME_LIMIT_SECONDS == 30
    assert settings.SOLVER_WORKERS == 4
    assert settings.SOLVER_RANDOM_SEED == 42
    assert settings.DEBUG is False
