from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Catalyst, ContractHistory, DormantBet, Price
from eigenview.factors.base import FactorResult

log = structlog.get_logger(__name__)

_FACTOR_ID = "dormant"

# All size/IV signals are RELATIVE to the ticker's own chain (percentile rank),
# so they work the same on a $50 mid-cap and a $1,000 mega-cap. Absolute dollar
# cutoffs are gone. Signal 5 (activation burst) still deferred (needs V/OI history).
#
# Max raw score: size(2) + cheap_IV(1) + catalyst(2) + time_left(1) + long_dated(1) = 7.
# Isolation is a multiplier (0.0 / 0.5 / 1.0) applied to the raw score.
_MAX_SCORE = 7

_STRIKE_BAND = 3            # ±3 strikes for the isolation window
_SIZE_PCT_1 = 0.90         # ΔWOI percentile within ticker for +1
_SIZE_PCT_2 = 0.99         # ΔWOI percentile within ticker for +2
_IV_CHEAP_PCT = 0.20       # IV in bottom 20% of the expiry = cheap (informed buyer)


@dataclass
class _ChainRow:
    """Minimal chain-row interface. Accepts ORM Chain rows and test rows alike."""
    strike: float
    call_put: str
    oi: int | None
    delta: float | None = None
    iv: float | None = None
    expiry: date | None = None


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
_TRADEABILITY_DWOI = 1_000_000.0   # absolute floor: confirm a real position exists
_SIZE_FILTER_PCT = 0.80            # bigness: ΔWOI in the ticker's top 20%
_DEEP_ITM_DELTA = 0.85             # |delta| above this = stock substitute, not a bet


def candidate_dwoi_floor(ticker_chain: list, spot: float) -> float:
    """ΔWOI cutoff for 'a big bet on this ticker': max(tradeability floor, 80th pct)."""
    dwois = [
        dwoi(getattr(c, "delta", None), getattr(c, "oi", None), spot)
        for c in ticker_chain
        if getattr(c, "oi", None)
    ]
    return max(_TRADEABILITY_DWOI, percentile_value(dwois, _SIZE_FILTER_PCT))


def is_dormant_candidate(
    contract, spot: float, floor: float, today: date, min_dte: int = 20
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


def isolation_multiplier(
    candidate, expiry_chain: list, spot: float, strike_band: int = _STRIKE_BAND
) -> tuple[float, float]:
    """Directional-purity gate over ±`strike_band` strikes on the candidate's expiry.

    Sums signed dollar-delta (calls +, puts -). A naked bet keeps its delta
    (|net| ≈ gross → purity ≈ 1); a collar/hedge cancels (purity ≈ 0).
    Returns (multiplier, purity): ≥0.7 →1.0, 0.3-0.7 →0.5, <0.3 →0.0 (drop).
    """
    strikes = sorted({float(c.strike) for c in expiry_chain})
    if not strikes:
        return 1.0, 1.0
    cand_strike = float(candidate.strike)
    ci = min(range(len(strikes)), key=lambda i: abs(strikes[i] - cand_strike))
    band = set(strikes[max(0, ci - strike_band): ci + strike_band + 1])

    net = gross = 0.0
    for c in expiry_chain:
        if float(c.strike) not in band:
            continue
        sign = 1.0 if _is_call(c.call_put) else -1.0
        d = sign * _delta_usd(getattr(c, "delta", None), getattr(c, "oi", None), spot)
        net += d
        gross += abs(d)

    if gross <= 0:
        return 1.0, 1.0  # no delta data — cannot prove a hedge, treat as isolated
    purity = abs(net) / gross
    if purity >= 0.7:
        return 1.0, purity
    if purity >= 0.3:
        return 0.5, purity
    return 0.0, purity


def _candidate_row(bet: DormantBet, expiry_chain: list):
    cp1 = str(bet.call_put).upper()[:1]
    return next(
        (c for c in expiry_chain
         if float(c.strike) == float(bet.strike) and _is_call(c.call_put) == (cp1 == "C")),
        None,
    )


def _build_chain_index(current_chains: list) -> dict[tuple[float, str], int]:
    """Map (strike, call_put) → current OI from today's chain snapshot."""
    index: dict[tuple[float, str], int] = {}
    for row in current_chains:
        index[(float(row.strike), str(row.call_put))] = int(row.oi or 0)
    return index


def score_bet_v2(
    bet: DormantBet,
    ticker_chain: list,
    spot: float,
    catalyst_near: bool,
) -> tuple[float, dict]:
    """Score one dormant bet. All size/IV signals are relative to the ticker's
    own chain. Isolation gates first (fully hedged → 0).

    `ticker_chain` is the full chain for the ticker (all strikes/expiries).
    Returns (final_score, detail).
    """
    expiry_chain = [c for c in ticker_chain if getattr(c, "expiry", None) == bet.expiry]

    mult, purity = isolation_multiplier(bet, expiry_chain, spot)
    detail: dict = {"hedge_purity": round(purity, 3), "isolation_multiplier": mult}
    if mult == 0.0:
        detail["isolation"] = "fully_hedged"
        return 0.0, detail

    cand = _candidate_row(bet, expiry_chain)
    cand_delta = getattr(cand, "delta", None) if cand is not None else None
    cand_oi = (getattr(cand, "oi", None) if cand is not None else None) or bet.original_oi or 0

    raw = 0

    # Size — ΔWOI percentile across the whole ticker chain (relative bigness)
    cand_dwoi = dwoi(cand_delta, cand_oi, spot)
    all_dwoi = [dwoi(getattr(c, "delta", None), getattr(c, "oi", None), spot)
                for c in ticker_chain if getattr(c, "oi", None)]
    size_pct = percentile_rank(cand_dwoi, all_dwoi)
    detail["dwoi_usd"] = round(cand_dwoi)
    detail["size_pct"] = round(size_pct, 3)
    if size_pct >= _SIZE_PCT_1:
        raw += 1
    if size_pct >= _SIZE_PCT_2:
        raw += 1

    # Cheap IV — IV percentile within the same expiry (informed buyer below the curve)
    iv_pct = None
    cand_iv = getattr(cand, "iv", None) if cand is not None else None
    if cand_iv is not None:
        ivs = [c.iv for c in expiry_chain if getattr(c, "iv", None) is not None]
        iv_pct = percentile_rank(float(cand_iv), [float(v) for v in ivs])
        detail["iv_pct"] = round(iv_pct, 3)
        if iv_pct <= _IV_CHEAP_PCT:
            raw += 1

    # Catalyst within 14 days
    if catalyst_near:
        raw += 2
    # Time remaining
    if bet.expiry and bet.expiry > date.today() + timedelta(days=7):
        raw += 1
    # Long-dated at open
    if bet.expiry and bet.original_date and (bet.expiry - bet.original_date).days >= 90:
        raw += 1

    detail["raw_score"] = raw
    detail["structural_score"] = (
        (1 if size_pct >= _SIZE_PCT_1 else 0)
        + (1 if size_pct >= _SIZE_PCT_2 else 0)
        + (1 if (iv_pct is not None and iv_pct <= _IV_CHEAP_PCT) else 0)
    )
    return raw * mult, detail


async def _has_catalyst_near(ticker: str, session: AsyncSession, days: int = 14) -> bool:
    rows = await session.execute(
        select(Catalyst).where(
            Catalyst.ticker == ticker,
            Catalyst.days_from_now >= 0,
            Catalyst.days_from_now <= days,
        )
    )
    return rows.scalars().first() is not None


async def score_dormant(
    ticker: str,
    session: AsyncSession,
    spot_price: float,
    current_chains: list,
    days_of_history: int = 30,
) -> FactorResult:
    if days_of_history < 30:
        return FactorResult(
            factor_id=_FACTOR_ID,
            firing=False,
            strength=0.0,
            label="ACCUMULATING",
            narrative=(
                f"Chain history {days_of_history}/30 days. "
                "Dormant radar activates after 30 days of data."
            ),
        )

    rows = await session.execute(select(DormantBet).where(DormantBet.ticker == ticker))
    bets = rows.scalars().all()

    if not bets:
        return FactorResult(
            factor_id=_FACTOR_ID, firing=False, strength=0.0, label="ACCUMULATING",
            detail={}, narrative="No dormant bets tracked yet. Accumulating chain history.",
        )

    catalyst_near = await _has_catalyst_near(ticker, session)

    best_score = 0.0
    best_bet: DormantBet | None = None
    best_detail: dict = {}
    for bet in bets:
        s, detail = score_bet_v2(bet, current_chains, spot_price, catalyst_near)
        if s > best_score:
            best_score, best_bet, best_detail = s, bet, detail

    activation_probability = best_score / _MAX_SCORE
    fires = activation_probability >= settings.dormant_firing_threshold

    if best_bet is None:
        return FactorResult(
            factor_id=_FACTOR_ID, firing=False, strength=0.0, label="DORMANT",
            detail={"reason": "all_candidates_hedged"},
            narrative="All tracked positions are hedged — no isolated directional bet.",
        )

    premium_m = (best_bet.original_premium or 0) / 1_000_000
    parts = [
        f"Dormant ${premium_m:.1f}M {best_bet.call_put} at ${best_bet.strike:.0f} "
        f"(exp {best_bet.expiry}) — score {best_score:.1f}/{_MAX_SCORE}."
    ]
    if best_detail.get("size_pct", 0) >= _SIZE_PCT_1:
        parts.append(f"ΔWOI in {best_detail['size_pct']*100:.0f}th pct for ticker.")
    if best_detail.get("iv_pct") is not None and best_detail["iv_pct"] <= _IV_CHEAP_PCT:
        parts.append("IV cheap vs its expiry (informed-buyer signal).")
    if catalyst_near:
        parts.append("Catalyst within 14 days.")
    if best_detail.get("isolation_multiplier", 1.0) == 0.5:
        parts.append("Partially hedged (score halved).")

    return FactorResult(
        factor_id=_FACTOR_ID,
        firing=fires,
        strength=activation_probability,
        label="ACTIVE" if fires else "DORMANT",
        detail={
            "activation_probability": round(activation_probability, 3),
            "best_bet_strike": best_bet.strike,
            "best_bet_expiry": str(best_bet.expiry),
            "best_score": round(best_score, 2),
            **best_detail,
        },
        narrative=" ".join(parts),
    )


async def score_dormant_from_history(
    ticker: str,
    session: AsyncSession,
    spot_price: float,
    current_chains: list,
    target: date | None = None,
) -> FactorResult:
    """Score dormant bets using activation engine (contract_history).

    Uses real baseline→recent comparison via score_activation(). Falls back to
    static score_bet_v2 if contract_history is insufficient (<15 rows).
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

    catalyst_near = await _has_catalyst_near(ticker, session)

    best_score = 0.0
    best_result = None
    best_bet: DormantBet | None = None
    activation_used = False

    for osi, bet in bet_by_osi.items():
        hist = hist_by_osi.get(osi, [])
        if len(hist) >= 15:
            activation_used = True
            act = score_activation(hist, underlying, bet.call_put, target)
            if act.strength > best_score:
                best_score = act.strength
                best_result = act
                best_bet = bet
        else:
            s, _ = score_bet_v2(bet, current_chains, spot_price, catalyst_near)
            normalized = s / _MAX_SCORE
            if not activation_used and normalized > best_score:
                best_score = normalized
                best_bet = bet

    # Not enough contract_history anywhere — use static fallback
    if not activation_used:
        return await score_dormant(ticker, session, spot_price, current_chains, 30)

    if best_result is None or not best_result.fired:
        return FactorResult(
            factor_id=_FACTOR_ID, firing=False, strength=best_score, label="DORMANT",
            detail={"bets_checked": len(bet_by_osi), "activation_ran": True},
            narrative="Dormant positions tracked — no activation signals firing.",
        )

    assert best_bet is not None
    premium_m = (best_bet.original_premium or 0) / 1_000_000
    parts = [
        f"Dormant ${premium_m:.1f}M {best_bet.call_put} at ${best_bet.strike:.0f} "
        f"(exp {best_bet.expiry}) — activation {best_result.strength:.0%}."
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
            "activation_probability": round(best_result.strength, 3),
            "triggers": best_result.triggers,
            "age_days": best_result.age_days,
            "born_on": str(best_result.born_on) if best_result.born_on else None,
            "best_bet_strike": best_bet.strike,
            "best_bet_expiry": str(best_bet.expiry),
            **best_result.detail,
        },
        narrative=" ".join(parts),
    )
