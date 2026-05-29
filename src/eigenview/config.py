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
    universe: str = "ndx100"
    daily_scan_hour: int = 8
    max_picks: int = 10
    macro_regime_green_threshold: int = 7
    macro_regime_red_threshold: int = 3

    # Factor thresholds — tune without code changes
    dormant_firing_threshold: float = 0.5
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

    # Tier-D (strong single-signal) thresholds (synthesis/gate.py tier_score)
    tier_d_flow_strength: float = 0.70
    tier_d_dormant_strength: float = 0.60

    # COT (data/macro.py) — default futures instrument for CFTC COT fetch
    cot_default_instrument: str = "ES"

    # Sentiment novelty baseline (factors/sentiment.py) — expected articles/day
    sentiment_expected_articles_per_day: float = 1.0

    # ── Dormant screen (factors/dormant.py) ──
    dormant_strike_band: int = 3                    # ± strikes for isolation window
    dormant_size_pct_1: float = 0.90                # ΔWOI pct within ticker for +1
    dormant_size_pct_2: float = 0.99                # ΔWOI pct within ticker for +2
    dormant_iv_cheap_pct: float = 0.20              # IV in bottom pct of expiry = cheap
    dormant_tradeability_dwoi: float = 1_000_000.0  # absolute ΔWOI floor: real position
    dormant_size_filter_pct: float = 0.80           # candidate bigness: ΔWOI top 20%
    dormant_deep_itm_delta: float = 0.85            # |delta| above = stock substitute, drop
    dormant_min_dte: int = 20                       # min days-to-expiry for a candidate
    dormant_catalyst_days: int = 14                 # catalyst-near window
    # Liquidity gate (OI proxy until real options-volume history is pulled).
    # A ticker must carry at least this aggregate chain OI to be screened for
    # dormant bets / to fire. Illiquid names are skipped (NOT_LIQUID), never fire.
    dormant_min_ticker_oi: int = 5_000
    dormant_min_time_left_days: int = 7             # +1 if expiry beyond this many days
    dormant_long_dated_days: int = 90               # +1 if DTE-at-open >= this
    dormant_min_history_days: int = 30              # min chain history before radar activates

    # ── Activation engine (factors/activation.py) — baseline→recent jumps ──
    activation_recent_days: int = 10                # trailing days treated as "now"
    activation_oi_jump_pct: float = 0.75            # current OI >= this fraction above baseline
    activation_oi_min_delta: int = 1000             # ...and >= this many extra contracts
    activation_vol_mult: float = 10.0               # a recent day's vol >= this x baseline avg
    activation_vol_min: int = 1000                  # ...and >= this absolute
    activation_iv_jump_abs: float = 0.10            # IV >= this many vol points above baseline
    activation_und_move_pct: float = 0.15           # underlying move in the bet's direction
    activation_und_vol_mult: float = 1.5            # ...on >= this x baseline avg volume
    activation_age_oi_frac: float = 0.50            # born-on = first day OI hit this frac of peak
    activation_min_history: int = 30                # min contract-history rows to score
    activation_min_triggers: int = 2                # fire when >= this many triggers
    activation_max_triggers: int = 4                # strength denominator (oi/vol/iv/underlying)

    # ── Scanner (synthesis/scanner.py) ──
    scanner_min_oi: int = 500                       # min OI for a dormant candidate
    scanner_price_lookback_days: int = 200          # daily price window read for TA
    scanner_history_insert_chunk: int = 100         # ContractHistory bulk-insert chunk size
    scanner_history_backfill_days: int = 120        # initial Databento backfill window
    scanner_concurrency: int = 5                    # parallel ticker semaphore size
    scanner_ta_lookback_days: int = 3               # bars to walk back for a firing TA signal

    # ── Pick quality gates (each independently toggleable) ───────────────────
    # Set enable_* = false in .env to turn off individual filters without changing thresholds.
    min_avg_daily_dollar_volume: int = 15_000_000  # $15M ADV — options-tradeable minimum
                                                   # ($50M over-filters NDX: AMGN/ADBE/ISRG all below)
    enable_liquidity_filter: bool = True           # gate on min_avg_daily_dollar_volume

    min_rr_ratio: float = 3.0                      # minimum reward:risk ratio for any pick
    enable_rr_filter: bool = True                  # gate on min_rr_ratio

    rs_percentile_min: int = 50                    # longs: top 50% of universe by 20d RS;
                                                   # shorts: bottom 50%
    enable_rs_filter: bool = True                  # gate on rs_percentile_min


settings = Settings()
