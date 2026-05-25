from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from eigenview.config import settings
from eigenview.data.storage import AsyncSessionLocal, LlmLog, Pick

log = structlog.get_logger(__name__)
router = APIRouter()

_SYSTEM = """\
You are EigenView, an options-pick assistant for a swing/short-dated options trader.
Answer in 3-5 sentences. Always reference specific numbers when available.
Plain English — explain jargon on first use. Never recommend position size.
If asked to filter or change view, just describe what you would show.

Current picks context:
{picks_summary}
"""


async def _build_picks_summary(session) -> str:
    today = date.today()
    result = await session.execute(
        select(Pick).where(Pick.date == today).order_by(Pick.conviction.desc()).limit(5)
    )
    picks = result.scalars().all()
    if not picks:
        return "No picks today yet. Run eigenview daily-scan first."
    lines = []
    for p in picks:
        factors_str = ""
        if p.factors_json:
            try:
                f = json.loads(p.factors_json)
                firing = [k for k, v in f.items() if v.get("firing")]
                factors_str = f" [{', '.join(firing)}]"
            except Exception as exc:
                log.warning("chat_factors_parse_error", ticker=p.ticker, error=str(exc))
        lines.append(
            f"- {p.ticker}: conviction {p.conviction}/5, {p.setup_type}, "
            f"entry ${p.entry_low}–${p.entry_high}, stop ${p.stop}{factors_str}"
        )
    return "\n".join(lines)


async def _stream_response(question: str, ticker: str | None, picks_summary: str) -> AsyncGenerator[str, None]:
    from anthropic import AsyncAnthropic, APIError

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    system = _SYSTEM.format(picks_summary=picks_summary)
    if ticker:
        system += f"\nCurrently selected pick: {ticker}"

    full_response = []
    try:
        async with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": question}],
        ) as stream:
            async for text in stream.text_stream:
                full_response.append(text)
                yield f"data: {json.dumps(text)}\n\n"
        yield "data: [DONE]\n\n"

        # Log
        response_text = "".join(full_response)
        async with AsyncSessionLocal() as session:
            session.add(LlmLog(
                call_type="chat",
                ticker=ticker,
                prompt=question,
                response=response_text,
                model="claude-sonnet-4-6",
            ))
            await session.commit()

    except Exception as exc:
        log.warning("chat_stream_error", error=str(exc))
        yield f"data: {json.dumps('Sorry, AI temporarily unavailable. Retry in a moment.')}\n\n"
        yield "data: [DONE]\n\n"


class ChatRequest(BaseModel):
    question: str
    ticker: str | None = None
    context: dict = {}


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    async with AsyncSessionLocal() as session:
        picks_summary = await _build_picks_summary(session)

    return StreamingResponse(
        _stream_response(req.question, req.ticker, picks_summary),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
