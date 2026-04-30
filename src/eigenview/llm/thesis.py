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


def _factor_summary(factors: dict) -> str:
    parts = []
    for fid, fdata in factors.items():
        label = fdata.get("label", "")
        detail = fdata.get("detail", {})
        firing = fdata.get("firing", False)
        if not firing:
            continue
        nums = []
        for k, v in detail.items():
            if isinstance(v, float | int) and k not in ("swing_high", "swing_low"):
                nums.append(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}")
        detail_str = f"({', '.join(nums[:3])})" if nums else ""
        parts.append(f"{fid}={label} {detail_str}".strip())
    return "; ".join(parts) if parts else "multiple factors firing"


def _fallback(ticker: str, factors: dict) -> str:
    ta = factors.get("technical", {}).get("label", "pattern")
    gex = factors.get("gex", {}).get("label", "gex")
    n = sum(1 for fid, f in factors.items() if f.get("firing") and fid not in ("technical", "gex", "macro_regime"))
    return f"{ticker} fires: TA ({ta}) + GEX ({gex}) gates passed with {n}/3 soft factors aligned."


async def generate_thesis(
    ticker: str,
    factors: dict,
    price: float,
    catalyst: str | None,
) -> str:
    summary = _factor_summary(factors)
    prompt = (
        f"You are writing a trade thesis for a swing/short-dated options pick.\n"
        f"Constraints: 2-3 sentences max. Reference at least 2 specific factor numbers. "
        f"Plain English. No hedging language.\n\n"
        f"Factors firing on {ticker}: {summary}\n"
        f"Current price: ${price:.2f}\n"
        f"Catalyst: {catalyst or 'none'}\n\n"
        f"Write the thesis."
    )
    try:
        client = _get_client()
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        thesis = msg.content[0].text.strip()
        input_tokens = msg.usage.input_tokens
        output_tokens = msg.usage.output_tokens

        async with AsyncSessionLocal() as session:
            session.add(LlmLog(
                call_type="thesis",
                ticker=ticker,
                prompt=prompt,
                response=thesis,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model="claude-sonnet-4-6",
            ))
            await session.commit()

        return thesis
    except APIError as exc:
        log.warning("thesis_api_error", ticker=ticker, error=str(exc))
        return _fallback(ticker, factors)
    except Exception as exc:
        log.warning("thesis_error", ticker=ticker, error=str(exc))
        return _fallback(ticker, factors)
