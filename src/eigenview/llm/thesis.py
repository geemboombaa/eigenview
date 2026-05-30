from __future__ import annotations

import structlog
from anthropic import AsyncAnthropic, APIError

from eigenview.config import settings
from eigenview.data.storage import AsyncSessionLocal, LlmLog

log = structlog.get_logger(__name__)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _evidence_lines(ctx: dict) -> list[str]:
    """Turn the firing factors into plain grounded evidence lines for the prompt."""
    factors = ctx.get("factors", {})
    lines: list[str] = []

    ta = factors.get("technical", {})
    if ta.get("firing"):
        d = ta.get("detail", {}) or {}
        wk = d.get("weekly_state")
        bits = [f"setup={ta.get('label')}"]
        if wk:
            bits.append(f"weekly trend={wk}")
        for k in ("rsi", "adx", "vol_ratio"):
            if isinstance(d.get(k), (int, float)):
                bits.append(f"{k}={_fmt(d[k])}")
        lines.append("Technical: " + ", ".join(bits))

    gex = factors.get("gex", {})
    if gex.get("firing"):
        d = gex.get("detail", {}) or {}
        bits = [f"regime={gex.get('label')}"]
        for k in ("gamma_flip", "call_wall", "put_wall"):
            if isinstance(d.get(k), (int, float)):
                bits.append(f"{k}={_fmt(d[k])}")
        lines.append("Dealer gamma: " + ", ".join(bits))

    flow = factors.get("flow", {})
    if flow.get("firing"):
        lines.append(f"Options flow: {flow.get('label')}")

    dorm = factors.get("dormant", {})
    if dorm.get("firing"):
        d = dorm.get("detail", {}) or {}
        trg = d.get("triggers") or []
        fired = d.get("triggers_fired")
        mx = d.get("triggers_max")
        tail = f" ({fired} of {mx} signals: {', '.join(trg)})" if trg else ""
        lines.append(f"Dormant position: {dorm.get('label')}{tail}")

    sent = factors.get("sentiment", {})
    if sent.get("firing"):
        d = sent.get("detail", {}) or {}
        hl = d.get("top_headline")
        net = d.get("net")
        bit = f"News sentiment: {sent.get('label')}"
        if isinstance(net, (int, float)):
            bit += f" (net {net:+.2f})"
        if hl:
            bit += f' — latest headline: "{hl}"'
        lines.append(bit)

    return lines


def _build_prompt(ctx: dict) -> str:
    direction = ctx["direction"]
    side = "LONG (bullish)" if direction == "long" else "SHORT (bearish)"
    instrument = "call options / call spread" if direction == "long" else "put options / put spread"
    ev = "\n".join(f"  - {ln}" for ln in _evidence_lines(ctx))
    macro = ctx.get("macro_label") or "unknown"
    cat = ctx.get("catalyst") or "none"

    def _n(v):
        return f"${v:.2f}" if isinstance(v, (int, float)) else "n/a"

    return (
        "You write the trade thesis a swing/options trader reads before acting. "
        "It must be grounded ONLY in the evidence below — invent nothing.\n\n"
        "HARD CONSTRAINTS (never violate):\n"
        f"  - This is a {side} trade on {ctx['ticker']}. The thesis MUST argue this direction. "
        f"Never suggest the opposite side or {('puts' if direction == 'long' else 'calls')}.\n"
        f"  - Instrument bias: {instrument}.\n"
        f"  - Entry zone {_n(ctx.get('entry_low'))}–{_n(ctx.get('entry_high'))}, "
        f"stop {_n(ctx.get('stop'))}, target {_n(ctx.get('target'))}, "
        f"R:R {_fmt(ctx['rr']) if isinstance(ctx.get('rr'), (int, float)) else 'n/a'}, "
        f"conviction {ctx.get('conviction', 'n/a')}/5.\n"
        f"  - Current price {_n(ctx.get('price'))}. Macro regime: {macro}. Catalyst: {cat}.\n\n"
        f"EVIDENCE (the only facts you may use):\n{ev}\n\n"
        "WRITE 3–4 sentences doing ALL of:\n"
        "  1. The causal story — connect the firing factors into one reason this trade sets up now.\n"
        "  2. The news/catalyst angle — if a headline or catalyst is present, tie it in; if not, say the setup is purely technical.\n"
        f"  3. Invalidation — state plainly that a {'close below' if direction == 'long' else 'close above'} the stop ({_n(ctx.get('stop'))}) kills the thesis.\n"
        "  4. Honesty — if any evidence conflicts with the direction (e.g. macro or sentiment leans the other way), name that risk in one clause.\n\n"
        "Plain English, specific numbers, no generic filler, no disclaimers."
    )


_LONG_CONTRADICTIONS = (
    "buy put", "buy puts", "bear put", "put spread", "short setup", "go short",
    "shorting", "sell calls", "bearish setup", "downtrend continuation",
)
_SHORT_CONTRADICTIONS = (
    "buy call", "buy calls", "bull call", "call spread", "long setup", "go long",
    "buying calls", "sell puts", "bullish setup", "uptrend continuation",
)


def _contradicts(direction: str, text: str) -> bool:
    """True if the prose advocates the opposite side of the computed direction."""
    t = text.lower()
    markers = _LONG_CONTRADICTIONS if direction == "long" else _SHORT_CONTRADICTIONS
    return any(m in t for m in markers)


def _fallback(ctx: dict) -> str:
    f = ctx.get("factors", {})
    ta = f.get("technical", {}).get("label", "pattern")
    gex = f.get("gex", {}).get("label", "gex")
    n = sum(1 for fid, fd in f.items()
            if fd.get("firing") and fid not in ("technical", "gex", "macro_regime"))
    side = "long" if ctx["direction"] == "long" else "short"
    return (f"{ctx['ticker']} {side} — {ta} with {gex} dealer gamma; "
            f"{n}/3 soft factors aligned. Invalidates on a close through "
            f"${ctx.get('stop'):.2f}." if isinstance(ctx.get('stop'), (int, float))
            else f"{ctx['ticker']} {side} — {ta} + {gex}; {n}/3 soft factors aligned.")


async def _call(prompt: str) -> tuple[str, int, int]:
    client = _get_client()
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=320,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip(), msg.usage.input_tokens, msg.usage.output_tokens


async def generate_thesis(ctx: dict) -> str:
    """Generate a grounded, direction-correct thesis.

    ctx keys: ticker, direction ('long'|'short'), setup, entry_low, entry_high,
    stop, target, rr, conviction, price, catalyst, macro_label, factors.
    Guardrail: if the prose advocates the opposite side, regenerate once; if it
    still contradicts (or the API fails), fall back to the safe template.
    """
    ticker = ctx["ticker"]
    direction = ctx["direction"]
    prompt = _build_prompt(ctx)
    try:
        thesis, in_tok, out_tok = await _call(prompt)
        used_prompt = prompt
        if _contradicts(direction, thesis):
            log.warning("thesis_direction_conflict_retry", ticker=ticker, direction=direction)
            retry_prompt = prompt + (
                f"\n\nYOUR PREVIOUS DRAFT ARGUED THE WRONG SIDE. "
                f"This is a {direction.upper()} trade. Rewrite arguing {direction} only."
            )
            thesis, in_tok, out_tok = await _call(retry_prompt)
            used_prompt = retry_prompt
            if _contradicts(direction, thesis):
                log.warning("thesis_direction_conflict_fallback", ticker=ticker)
                return _fallback(ctx)

        async with AsyncSessionLocal() as session:
            session.add(LlmLog(
                call_type="thesis", ticker=ticker, prompt=used_prompt, response=thesis,
                input_tokens=in_tok, output_tokens=out_tok, model="claude-sonnet-4-6",
            ))
            await session.commit()
        return thesis
    except APIError as exc:
        log.warning("thesis_api_error", ticker=ticker, error=str(exc))
        return _fallback(ctx)
    except Exception as exc:
        log.warning("thesis_error", ticker=ticker, error=str(exc))
        return _fallback(ctx)
