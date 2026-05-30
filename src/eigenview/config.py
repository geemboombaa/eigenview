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
    macro_regime_green_threshold: int = 7
    macro_regime_red_threshold: int = 3
    # Macro regime per-signal thresholds + weights (factors/macro_regime.py) — no hardcode.
    macro_dix_bullish_threshold: float = 0.43   # DIX > this = dark-pool buying (calibrated 2026-04-29)
    macro_vix_low_threshold: float = 20.0       # VIX m1 < this = low-vol regime
    macro_weight_gex: int = 3                    # points for positive net GEX
    macro_weight_contango: int = 2              # points for VIX contango (term structure up)
    macro_weight_dix: int = 3                    # points for DIX above threshold
    macro_weight_vix: int = 2                    # points for low VIX

    # Factor thresholds — tune without code changes
    dormant_firing_threshold: float = 0.5
    flow_min_premium_usd: float = 500_000
    flow_min_voi_ratio: float = 3.0
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

    # ── News refresh job (cli.py fetch-news) — decoupled from daily scan ──
    news_refresh_concurrency: int = 8       # parallel ticker semaphore (Finnhub ~60 req/min)
    news_av_daily_budget: int = 20          # max tickers routed through Alpha Vantage/day
                                            # (AV free = 25/day; reserve headroom)
    news_lookback_days: int = 3             # how far back each refresh pulls per ticker

    # Sentiment novelty baseline (factors/sentiment.py) — expected articles/day
    sentiment_expected_articles_per_day: float = 1.0
    # Sentiment model (factors/sentiment_model.py) — FinBERT-tone primary (benchmark 2026-05-29:
    # 74% agreement w/ ProsusAI, finance-tuned, 40ms/headline CPU), VADER lexicon fallback.
    sentiment_model_id: str = "yiyanghkust/finbert-tone"
    sentiment_min_articles: int = 1              # min recent articles to score at all
    sentiment_neutral_deadzone: float = 0.05     # |net| within this = neutral (no direction, no fire)
    sentiment_recency_halflife_days: float = 2.0 # article weight halves every N days old
    sentiment_batch_size: int = 16               # FinBERT inference batch — heavy-news names (100s of articles) finish fast

    # ── Dormant screen (factors/dormant.py) ──
    dormant_tradeability_dwoi: float = 25_000_000.0  # absolute ΔWOI floor: a real whale position
                                                     #   (calibrated 2026-05-30 — $1M kept 18k junk
                                                     #   contracts; $25M + top2% lands ~1.05k watchlist)
    dormant_size_filter_pct: float = 0.98           # candidate bigness: ΔWOI top 2% of ticker chain
    dormant_deep_itm_delta: float = 0.85            # |delta| above = stock substitute, drop
    dormant_min_dte: int = 20                       # min days-to-expiry for a candidate
    # Liquidity gate (OI proxy until real options-volume history is pulled).
    # A ticker must carry at least this aggregate chain OI to be screened for
    # dormant bets / to fire. Illiquid names are skipped (NOT_LIQUID), never fire.
    dormant_min_ticker_oi: int = 5_000

    # ── Bet-confidence soft annotation (factors/dormant.py bet_confidence) ──
    # Static vertical/calendar "spread" detection was REMOVED 2026-05-30: from a single
    # EOD OI snapshot those checks fire on LIQUIDITY, not real spreads (86–88% false-fire
    # on liquid chains, killing genuine LEAP bets). A spread leg vs two independent holders
    # at the same strike is indistinguishable in one snapshot — only ΔOI-correlation across
    # consecutive daily snapshots can tell them apart (deferred until snapshots accrue).
    # List size is now controlled purely by the dollar/percentile SIZE screen above.
    # bet_confidence keeps ONLY the whole-chain delta-balance flag as a soft annotation
    # (penalty 0.7 stays above the 0.40 min, so it never drops a contract — display only).
    dormant_bet_confidence_min: float = 0.40        # keep contract if confidence >= this
    dormant_chain_balance_purity: float = 0.30      # whole-chain |net|/gross delta below this = balanced book
    dormant_pen_chain_balanced: float = 0.7         #   → confidence ×= this (soft: stays above min)

    # ── Activation engine (factors/activation.py) — baseline→recent jumps ──
    # Thresholds calibrated 2026-05-30 to realistic activation moves (old 75%/10x/15%/10pt
    # required two near-extreme events at once and almost never fired). See docs/15.
    activation_recent_days: int = 10                # trailing days treated as "now"
    activation_oi_jump_pct: float = 0.30            # current OI >= this fraction above baseline
    activation_oi_min_delta: int = 500              # ...and >= this many extra contracts
    activation_vol_mult: float = 3.0                # a recent day's vol >= this x baseline avg
    activation_vol_min: int = 500                   # ...and >= this absolute
    activation_iv_jump_abs: float = 0.05            # IV >= this many vol points above baseline
    activation_und_move_pct: float = 0.05           # underlying move in the bet's direction
    activation_und_vol_mult: float = 1.4            # ...on >= this x baseline avg volume
    activation_age_oi_frac: float = 0.50            # born-on = first day OI hit this frac of peak
    activation_min_history: int = 30                # >= this many points → lookback mode (else forward)
    activation_forward_min: int = 2                 # min points to compare at all (forward mode floor)
    activation_lookback_days: int = 30              # window: only the last N days of the series are scored
    activation_min_triggers: int = 2                # fire when >= this many triggers
    activation_max_triggers: int = 4                # strength denominator (oi/vol/iv/underlying)

    # ── Scanner (synthesis/scanner.py) ──
    scanner_min_oi: int = 500                       # min OI for a dormant candidate
    scanner_price_lookback_days: int = 200          # daily price window read for TA
    scanner_history_insert_chunk: int = 100         # ContractHistory bulk-insert chunk size
    scanner_history_backfill_days: int = 180        # per-contract Databento backfill window (6mo)
    scanner_history_symbol_batch: int = 25          # symbols per Databento get_range call — small so a
                                                    #   180d pull finishes well inside the per-call timeout
                                                    #   (130 syms × 180d in one call hung >180s; root cause)
    scanner_history_call_timeout_secs: float = 120.0 # hard bound per get_range sub-batch — no silent hang
    scanner_history_fetch_concurrency: int = 3      # parallel sub-batch calls (Databento throttles >3 → 504)
    scanner_history_window_days: int = 45           # split a long backfill into <=N-day date windows —
                                                    #   the failure axis is window DEPTH (a 180d pull hangs
                                                    #   even at 25 syms; short windows always returned fast)
    scanner_concurrency: int = 5                    # parallel ticker semaphore size
    scanner_ta_lookback_days: int = 3               # bars to walk back for a firing TA signal
    scanner_universe: str = "both"                  # default scan scope: ndx100 | sp500 | both
    scanner_chunk_size: int = 10                    # tickers scored + committed per chunk (live progress)
    scanner_ticker_timeout_secs: int = 45           # per-ticker hard timeout — one bad name can't stall the run

    # ── Download-scope filter (cli.py fetch-data) — pull data ONLY for tradeable names ──
    # Applied to the NDX∪SP500 universe BEFORE download: build the keep-list, then fetch.
    download_min_atr: float = 1.0           # ATR14 in $ — below this the name is too quiet
                                            #   to trade a defined-risk options setup (reason:
                                            #   stop/target distances collapse under ~$1 ATR)
    download_earnings_blackout_days: int = 5  # skip names with earnings within N days — binary
                                            #   event risk swamps the technical setup
    download_options_volume_min: int = 2000  # avg daily option volume floor; applied only where
                                            #   chains.volume is populated (≈85% null in Databento
                                            #   OPRA statistics) — OI gate below is the real proxy
    # OI≥dormant_min_ticker_oi (5000) is reused as the liquidity proxy for download scope.
    download_concurrency: int = 3           # chunks fetched concurrently (gather + semaphore).
                                            #   3 because a single 504 already appeared at serial
                                            #   pace — Databento throttles; >3 raises 504/429 risk

    # ── R:R conviction downgrade (synthesis/gate.py conviction_score) ─────────
    min_rr_ratio: float = 3.0                      # target/risk below this DOWNGRADES conviction
    enable_rr_filter: bool = True                  #   one tier (spec: downgrade, never eliminate)

    # ── Funnel-analysis ONLY (scripts/ta_firing_count.py) — NOT live-scan gates ──
    # These drive the standalone TA-firing funnel report, not qualify_pick/rank_picks.
    min_avg_daily_dollar_volume: int = 15_000_000  # $15M ADV — used by the funnel script
    enable_liquidity_filter: bool = True
    rs_percentile_min: int = 50                    # 20d relative-strength percentile (funnel script)
    enable_rs_filter: bool = True


settings = Settings()
