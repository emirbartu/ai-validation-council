"""Test config validation and settings loading."""


from council.config import Settings


class TestSettings:
    def test_default_values(self):
        settings = Settings()
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.qdrant_url == "http://localhost:6333"
        assert settings.llm_daily_limit == 50.0
        assert settings.max_analyses_per_user_per_day == 5
        assert settings.max_concurrent_analyses == 3

    def test_model_defaults_are_empty(self):
        settings = Settings()
        assert settings.market_analyst_model == ""
        assert settings.devils_advocate_model == ""
        assert settings.divergence_model == ""
        assert settings.report_model == ""

    def test_all_keys_optional(self):
        settings = Settings(
            llm_api_key="sk-test",
            serper_api_key="sk-test",
            database_url="postgresql+asyncpg://localhost/test",
            redis_url="redis://localhost:6379",
        )
        assert settings.llm_api_key is not None
        assert settings.environment == "development"

    def test_secret_str_masking(self):
        settings = Settings(llm_api_key="sk-or-v1-secret-key-12345")
        key = settings.llm_api_key
        assert key is not None
        assert key.get_secret_value() == "sk-or-v1-secret-key-12345"

    def test_env_var_overrides(self):
        settings = Settings(environment="production", log_level="DEBUG")
        assert settings.environment == "production"
        assert settings.log_level == "DEBUG"
