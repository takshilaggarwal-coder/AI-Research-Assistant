"""Central configuration (BONUS: Configuration Management).

All tunables live here and are sourced from environment variables / a local
``.env`` file. Nothing else in the codebase reads ``os.environ`` directly, so
there is exactly one place to look when wiring up a new deployment.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "ZyLabs AI Research Copilot"
    environment: str = "development"
    log_level: str = "INFO"
    # Comma-separated list of allowed CORS origins for the React dev server.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Persistence ---
    database_path: str = "copilot.db"
    checkpoint_path: str = "checkpoints.db"

    # --- LLM provider ---
    # If ANTHROPIC_API_KEY is empty the app runs in a fully deterministic
    # offline "stub" mode so it can be demoed with zero external dependencies.
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"
    llm_max_tokens: int = 2048

    # --- Web search provider ---
    # Preference order: Tavily (if key) -> DuckDuckGo (no key) -> offline stub.
    tavily_api_key: str = ""
    search_results_per_query: int = 4

    # --- Workflow tuning ---
    quality_threshold: float = 0.7
    max_research_retries: int = 1

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_mode(self) -> str:
        return "anthropic" if self.anthropic_api_key else "stub"

    @property
    def search_mode(self) -> str:
        if self.tavily_api_key:
            return "tavily"
        return "duckduckgo"  # falls back to stub at call time if unavailable


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so settings are parsed exactly once per process."""
    return Settings()
