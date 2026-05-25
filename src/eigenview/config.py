from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    alpha_vantage_key: str
    finnhub_key: str
    anthropic_api_key: str
    databento_key: str = ""

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

    # Risk-free rate — single source for all options pricing (BS mark, IV solve)
    risk_free_rate: float = 0.045

    # Conviction scoring (synthesis/gate.py conviction_score)
    conviction_strength_weight: float = 0.65
    conviction_count_weight: float = 0.35
    conviction_t5_threshold: float = 0.80
    conviction_t4_threshold: float = 0.60
    conviction_t3_threshold: float = 0.40
    conviction_t2_threshold: float = 0.20

    # Entry-zone / stop construction (synthesis/gate.py)
    entry_zone_long_frac: float = 0.30    # long band depth above swing_low, as frac of swing range
    entry_zone_short_frac: float = 0.15   # short band depth below swing_high, as frac of swing range
    stop_buffer_pct: float = 0.02         # stop = swing_low*(1-buf) long / swing_high*(1+buf) short
    swing_fallback_pct: float = 0.02      # fallback swing levels = spot*(1±this) when detail missing


settings = Settings()
