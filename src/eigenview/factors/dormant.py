from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Chain, ContractHistory, DormantBet, Price
from eigenview.factors.base import FactorResult

log = structlog.get_logger(__name__)

_FACTOR_ID = "dormant"

# All size signals are RELATIVE to the ticker's own chain (percentile rank), so
# they work the same on a $50 mid-cap and a $1,000 mega-cap. A big-OI contract is
# kept only if bet_confidence clears the hedge/spread filter at watchlist-write.


@dataclass
class _ChainRow:
    """Minimal chain-row interface. Accepts ORM Chain rows and test rows alike."""
    strike: float
    call_put: str
    oi: int | None
    delta: float | None = None
    iv: float | None = None
    expiry: date | None = None
    volume: int | None = None


def mark_price(
    bid: float | None, ask: float | None, iv: float | None,
    spot: float, strike: float, expiry: date | None, call_put: str, today: date,
) -> float:
    """Best available option mark: bid/ask mid, else Black-Scholes from IV.

    Databento EOD statistics carry bid/ask for only a minority of contracts, so
    premium must fall back to the BS price implied by the stored IV (which was
    itself solved from the close) — otherwise premium reads $0. See find_dormant.
    """
    b, a = bid or 0.0, ask or 0.0
    if b > 0 and a > 0:
        return (b + a) / 2.0
    if iv and iv > 0 and spot > 0 and expiry:
        from py_vollib.black_scholes import black_scholes
        t = max((expiry - today).days, 1) / 365.0
        try:
            return black_scholes(str(call_put).lower()[:1], spot, strike, t, settings.risk_free_rate, iv)
        except Exception as exc:
            log.warning("mark_price.bs_failed", spot=spot, strike=strike, iv=iv, t=t, call_put=call_put, error=str(exc))
            return 0.0
    return 0.0


def _delta_usd(delta: float | None, oi: int | None, spot: float) -> float:
    return abs(delta or 0.0) * float(oi or 0) * 100.0 * spot


def dwoi(delta: float | None, oi: int | None, spot: float) -> float:
    """Delta-weighted open interest in dollars: |delta| * OI * 100 * spot."""
    return _delta_usd(delta, oi, spot)


def _is_call(call_put) -> bool:
    return str(call_put).upper().startswith("C")


def percentile_rank(value: float, population: list[float]) -> float:
    """Fraction of the population strictly below `value` (0.0 - 1.0)."""
    if not population:
        return 0.0
    below = sum(1 for x in population if x < value)
    return below / len(population)


def percentile_value(values: list[float], q: float) -> float:
    """The value at the q-th percentile (0.0-1.0) of `values`."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(q * len(s)))
    return s[idx]


# ── Candidate selection (shared by the live scanner and the find_dormant script) ──
# A "dormant bet" candidate = a position big *relative to its own ticker's chain*,
# not an absolute dollar size — so it works on mid-caps and mega-caps alike.
_TRADEABILITY_DWOI = settings.dormant_tradeability_dwoi  # absolute floor: real position exists
_SIZE_FILTER_PCT = settings.dormant_size_filter_pct      # bigness: ΔWOI in the ticker's top pct
_DEEP_ITM_DELTA = settings.dormant_deep_itm_delta        # |delta| above this = stock substitute


def candidate_dwoi_floor(ticker_chain: list, spot: float) -> float:
    """ΔWOI cutoff for 'a big bet on this ticker': max(tradeability floor, 80th pct)."""
    dwois = [
        dwoi(getattr(c, "delta", None), getattr(c, "oi", None), spot)
        for c in ticker_chain
        if getattr(c, "oi", None)
    ]
    return max(_TRADEABILITY_DWOI, percentile_value(dwois, _SIZE_FILTER_PCT))


def is_dormant_candidate(
    contract, spot: float, floor: float, today: date, min_dte: int = settings.dormant_min_dte
) -> bool:
    """Qualify one contract: long-dated, big-relative-to-ticker, not deep-ITM."""
    expiry = getattr(contract, "expiry", None)
    if not expiry or (expiry - today).days < min_dte:
        return False
    if dwoi(getattr(contract, "delta", None), getattr(contract, "oi", None), spot) < floor:
        return False
    d = getattr(contract, "delta", None)
    if d is not None:
        if _is_call(contract.call_put) and d > _DEEP_ITM_DELTA:
            return False
        if not _is_call(contract.call_put) and d < -_DEEP_ITM_DELTA:
            return False
    return True


def _signed_delta_usd(c, spot: float) -> float:
    sign = 1.0 if _is_call(c.call_put) else -1.0
    return sign * _delta_usd(getattr(c, "delta", None), getattr(c, "oi", None), spot)


def bet_confidence(candidate, ticker_chain: list, spot: float) -> tuple[float, dict]:
    """Is a big-OI contract a STANDALONE directional bet, or part of a hedge/spread?

    Starts at confidence 1.0 and applies one multiplicative penalty per unambiguous
    hedge/spread structure detectable from an EOD chain alone:
      • same-side vertical : a comparable same-type OI leg within ±band strikes
      • cross-expiry calendar: comparable same-strike OI on a different expiry
      • balanced book      : the WHOLE ticker chain is delta-neutral (a dealer book,
                             not a directional position)
    No V/OI "newness" gate — a true dormant bet is old/large/quiet by design; newness
    belongs to the activation layer. Risk-reversals are directional, so not penalized.
    Returns (confidence, detail). Caller drops the contract if confidence < the min.
    """
    cand_oi = float(getattr(candidate, "oi", 0) or 0)
    if cand_oi <= 0:
        return 0.0, {"reason": "no_oi"}
    cand_strike = float(candidate.strike)
    cand_exp = getattr(candidate, "expiry", None)
    cand_is_call = _is_call(candidate.call_put)

    conf = 1.0
    detail: dict = {}

    # 1. Same-expiry, same-side vertical leg (long one strike, short another).
    same_side = [c for c in ticker_chain
                 if getattr(c, "expiry", None) == cand_exp
                 and _is_call(c.call_put) == cand_is_call]
    strikes = sorted({float(c.strike) for c in same_side})
    vert_oi = 0.0
    if cand_strike in strikes:
        ci = strikes.index(cand_strike)
        lo = strikes[max(0, ci - settings.dormant_vertical_strike_band)]
        hi = strikes[min(len(strikes) - 1, ci + settings.dormant_vertical_strike_band)]
        vert_oi = max(
            (float(c.oi or 0) for c in same_side
             if float(c.strike) != cand_strike and lo <= float(c.strike) <= hi),
            default=0.0,
        )
    detail["vertical_oi"] = round(vert_oi)
    if vert_oi >= settings.dormant_vertical_oi_frac * cand_oi:
        conf *= settings.dormant_pen_vertical
        detail["vertical"] = True

    # 2. Cross-expiry calendar/diagonal: same strike, same side, a different expiry.
    cal_oi = sum(
        float(c.oi or 0) for c in ticker_chain
        if _is_call(c.call_put) == cand_is_call
        and float(c.strike) == cand_strike
        and getattr(c, "expiry", None) != cand_exp
    )
    detail["calendar_oi"] = round(cal_oi)
    if cal_oi >= settings.dormant_calendar_oi_frac * cand_oi:
        conf *= settings.dormant_pen_calendar
        detail["calendar"] = True

    # 3. Whole-chain delta balance — a market-maker book nets to ~0, a real bet doesn't.
    net = gross = 0.0
    for c in ticker_chain:
        d = _signed_delta_usd(c, spot)
        net += d
        gross += abs(d)
    purity = abs(net) / gross if gross > 0 else 1.0
    detail["chain_purity"] = round(purity, 3)
    if purity < settings.dormant_chain_balance_purity:
        conf *= settings.dormant_pen_chain_balanced
        detail["chain_balanced"] = True

    detail["confidence"] = round(conf, 3)
    return conf, detail




def _group_chain_snapshots(rows) -> dict:
    """Group raw chain-snapshot rows (snapshot_date, strike, expiry, call_put, oi, volume, iv)
    into a forward series per contract, keyed by (strike, expiry, call_put-initial).

    One batched query per ticker feeds this — the forward baseline source (no Databento),
    growing one point per scan. Pure transform so it's unit-testable."""
    out: dict = {}
    for snap, strike, expiry, cp, oi, vol, iv in rows:
        key = (float(strike), expiry, str(cp).upper()[:1])
        out.setdefault(key, []).append({"date": snap, "oi": oi, "volume": vol, "close": None, "iv": iv})
    for series in out.values():
        series.sort(key=lambda r: r["date"])
    return out


def _merge_series(hist_ch: list[dict], snap: list[dict]) -> list[dict]:
    """Merge Databento contract_history with our chain-snapshot series, one row per
    date. contract_history wins on a shared date (authoritative per-contract stats)."""
    by_date: dict = {}
    for r in snap:
        by_date[r["date"]] = r
    for r in hist_ch:
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda r: r["date"])


async def score_dormant_from_history(
    ticker: str,
    session: AsyncSession,
    spot_price: float,
    current_chains: list,
    target: date | None = None,
) -> FactorResult:
    """Score dormant bets using the activation engine (contract_history).

    Real baseline→recent comparison via score_activation(): lookback mode when the
    merged series has ≥ activation_min_history points, forward mode (chain snapshots
    only, +1/scan) when fewer. No hedge filter here — hedged contracts are kept out
    of the watchlist at write-time by bet_confidence, so everything tracked is a bet.
    """
    from eigenview.factors.activation import score_activation
    from eigenview.data.databento_history import osi_symbol as _osi

    if target is None:
        target = date.today()

    bet_rows = await session.execute(select(DormantBet).where(DormantBet.ticker == ticker))
    bets = bet_rows.scalars().all()

    if not bets:
        return FactorResult(
            factor_id=_FACTOR_ID, firing=False, strength=0.0, label="ACCUMULATING",
            detail={}, narrative="No dormant bets tracked yet.",
        )

    # Underlying price series (for activation engine's directional move check)
    und_rows = await session.execute(
        select(Price)
        .where(Price.ticker == ticker.upper(), Price.timeframe == "1d")
        .order_by(Price.date.asc())
    )
    underlying = [
        {"date": r.date, "close": r.close, "volume": r.volume}
        for r in und_rows.scalars().all()
    ]

    # Map each bet to its OSI symbol and fetch contract history in one query
    bet_by_osi: dict[str, DormantBet] = {
        _osi(b.ticker, b.expiry, b.call_put, b.strike): b for b in bets
    }
    hist_rows = await session.execute(
        select(ContractHistory)
        .where(ContractHistory.osi_symbol.in_(list(bet_by_osi.keys())))
        .order_by(ContractHistory.date.asc())
    )
    hist_by_osi: dict[str, list[dict]] = {}
    for r in hist_rows.scalars().all():
        hist_by_osi.setdefault(r.osi_symbol, []).append(
            {"date": r.date, "oi": r.oi, "volume": r.volume, "close": r.close, "iv": r.iv}
        )

    # One query for ALL this ticker's stored chain snapshots → forward series per contract.
    snap_rows = await session.execute(
        select(Chain.snapshot_date, Chain.strike, Chain.expiry, Chain.call_put,
               Chain.oi, Chain.volume, Chain.iv)
        .where(Chain.ticker == ticker)
        .order_by(Chain.snapshot_date.asc())
    )
    snap_by_contract = _group_chain_snapshots(snap_rows.all())

    best_score = 0.0
    best_result = None
    best_bet: DormantBet | None = None
    scored_any = False

    for osi, bet in bet_by_osi.items():
        # Merge Databento past (where it exists) with our own forward chain snapshots.
        # score_activation handles both — lookback when >=30 pts, forward when fewer.
        key = (float(bet.strike), bet.expiry, str(bet.call_put).upper()[:1])
        series = _merge_series(hist_by_osi.get(osi, []), snap_by_contract.get(key, []))
        if len(series) >= settings.activation_forward_min:
            scored_any = True
        act = score_activation(series, underlying, bet.call_put, target)
        if best_result is None or act.strength > best_score:
            best_score = act.strength
            best_result = act
            best_bet = bet

    # No contract has >= 2 snapshots yet → just discovered, no baseline to compare.
    # Resolves on the next scan as chain snapshots accrue. NOT firing (nothing measured).
    if not scored_any:
        return FactorResult(
            factor_id=_FACTOR_ID, firing=False, strength=best_score, label="ACCUMULATING",
            detail={
                "bets_checked": len(bet_by_osi),
                "reason": "awaiting_baseline",
                "points": (best_result.detail.get("points", 0) if best_result else 0),
            },
            narrative=(
                "Dormant candidate tracked — fewer than 2 snapshots so far, no baseline "
                "to compare yet. Resolves as daily chain snapshots accrue."
            ),
        )

    fires = (
        best_result is not None
        and best_result.fired
        and best_result.strength >= settings.dormant_firing_threshold
    )
    if not fires:
        return FactorResult(
            factor_id=_FACTOR_ID, firing=False, strength=best_score, label="DORMANT",
            detail={"bets_checked": len(bet_by_osi), "activation_ran": True},
            narrative="Dormant positions tracked — no activation signals firing.",
        )

    assert best_bet is not None
    premium_m = (best_bet.original_premium or 0) / 1_000_000
    n_fired = len(best_result.triggers)
    parts = [
        f"Dormant ${premium_m:.1f}M {best_bet.call_put} at ${best_bet.strike:.0f} "
        f"(exp {best_bet.expiry}) — {n_fired} of {settings.activation_max_triggers} activation signals firing."
    ]
    if best_result.triggers:
        parts.append(f"Signals: {', '.join(best_result.triggers)}.")
    if best_result.age_days:
        parts.append(f"Position age: {best_result.age_days}d.")

    return FactorResult(
        factor_id=_FACTOR_ID,
        firing=True,
        strength=best_result.strength,
        label="ACTIVE",
        detail={
            # Not a probability — it's how many of N activation triggers fired (count/N).
            "activation_score": round(best_result.strength, 3),
            "triggers_fired": n_fired,
            "triggers_max": settings.activation_max_triggers,
            "triggers": best_result.triggers,
            "age_days": best_result.age_days,
            "born_on": str(best_result.born_on) if best_result.born_on else None,
            "best_bet_strike": best_bet.strike,
            "best_bet_expiry": str(best_bet.expiry),
            **best_result.detail,
        },
        narrative=" ".join(parts),
    )
