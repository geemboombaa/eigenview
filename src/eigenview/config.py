from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    supabase_url: str = ""
    supabase_secret_key: str = ""
    alpha_vantage_key: str
    finnhub_key: str
    anthropic_api_key: str

    log_level: str = "INFO"
    universe: str = "NDX100"
    daily_scan_hour: int = 8
    max_picks: int = 10
    macro_regime_green_threshold: int = 7
    macro_regime_red_threshold: int = 3

    # Factor thresholds — tune without code changes
    dormant_firing_threshold: float = 0.6
    flow_min_premium_usd: float = 500_000
    flow_min_voi_ratio: float = 3.0
    sentiment_novelty_z_threshold: float = 1.5
    ta_pattern_confidence_threshold: float = 0.6
    gex_short_gamma_threshold: float = 0.0


settings = Settings()
