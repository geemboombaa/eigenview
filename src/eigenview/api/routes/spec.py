from __future__ import annotations

import pathlib
import re

from fastapi import APIRouter
from sqlalchemy import text

from eigenview.data.storage import AsyncSessionLocal

router = APIRouter()


# ── /api/spec/ta ─────────────────────────────────────────────────────────────

@router.get("/spec/ta")
async def get_ta_spec() -> dict:
    return {
        "patterns": [
            {
                "name": "pullback_in_trend",
                "display_name": "Pullback to Support",
                "category": "Trend Continuation",
                "weekly_requirement": "BULLISH or BULLISH_EXTENDED",
                "conditions": [
                    {"id": "uptrend",      "label": "Uptrend intact",          "field": "trend",        "expected": "bullish"},
                    {"id": "rsi_dip",      "label": "RSI in dip zone",         "field": "rsi",          "check": "lte_rsi_p40"},
                    {"id": "adx_trending", "label": "ADX trending",            "field": "adx",          "check": "gte_15"},
                    {"id": "vol_light",    "label": "Volume light on pullback", "field": "vol_ratio",    "check": "lte_vol_p72"},
                    {"id": "weekly_ok",    "label": "Weekly context bullish",   "field": "weekly_state", "expected": ["BULLISH", "BULLISH_EXTENDED"]},
                ],
                "detail_fields": ["trend", "weekly_trend", "rsi", "rsi_p40", "adx", "vol_ratio", "swing_low", "weekly_state"],
            }
        ]
    }


# ── /api/audit/ta ─────────────────────────────────────────────────────────────

@router.get("/audit/ta")
async def audit_ta() -> dict:
    findings = []

    tech_path = pathlib.Path("src/eigenview/factors/technical.py")
    if not tech_path.exists():
        # Try relative to package root
        tech_path = pathlib.Path(__file__).parents[4] / "src" / "eigenview" / "factors" / "technical.py"

    if not tech_path.exists():
        return {
            "findings": [{"file": "technical.py", "check": "file found", "status": "FAIL", "detail": "technical.py not found"}],
            "summary": {"pass": 0, "fail": 1, "warn": 0},
        }

    tech_code = tech_path.read_text(encoding="utf-8")

    # Check 1: pullback_in_trend in detect_pattern
    if "pullback_in_trend" in tech_code and "detect_pattern" in tech_code:
        findings.append({"file": "technical.py", "check": "pullback_in_trend in detect_pattern", "status": "PASS", "detail": ""})
    else:
        findings.append({"file": "technical.py", "check": "pullback_in_trend in detect_pattern", "status": "FAIL", "detail": "pattern or function missing"})

    # Check 2: No hardcoded RSI threshold (< 32 or > 68)
    if re.search(r'rsif?\s*[<>]\s*3[2-9]|rsif?\s*[<>]\s*6[5-9]', tech_code):
        findings.append({"file": "technical.py", "check": "No hardcoded RSI literals", "status": "WARN", "detail": "Found old-style RSI comparison"})
    else:
        findings.append({"file": "technical.py", "check": "No hardcoded RSI literals", "status": "PASS", "detail": ""})

    # Check 3: squeeze_pro in use
    if "squeeze_pro" in tech_code:
        findings.append({"file": "technical.py", "check": "squeeze_pro() in use", "status": "PASS", "detail": ""})
    else:
        findings.append({"file": "technical.py", "check": "squeeze_pro() in use", "status": "FAIL", "detail": "squeeze_pro not found"})

    # Check 4: rsi_p40 in detail dict
    if "rsi_p40" in tech_code:
        findings.append({"file": "technical.py", "check": "rsi_p40 in detail dict", "status": "PASS", "detail": ""})
    else:
        findings.append({"file": "technical.py", "check": "rsi_p40 in detail dict", "status": "FAIL", "detail": "rsi_p40 not in detail"})

    # Check 5: weekly_state in detail dict
    if "weekly_state" in tech_code:
        findings.append({"file": "technical.py", "check": "weekly_state in detail dict", "status": "PASS", "detail": ""})
    else:
        findings.append({"file": "technical.py", "check": "weekly_state in detail dict", "status": "FAIL", "detail": "weekly_state not in detail"})

    summary = {
        "pass": sum(1 for f in findings if f["status"] == "PASS"),
        "fail": sum(1 for f in findings if f["status"] == "FAIL"),
        "warn": sum(1 for f in findings if f["status"] == "WARN"),
    }
    return {"findings": findings, "summary": summary}


# ── /api/spec/notes  (POST) ──────────────────────────────────────────────────

from pydantic import BaseModel  # noqa: E402


class NotePayload(BaseModel):
    spec_id: str
    note: str


@router.post("/spec/notes")
async def save_spec_note(payload: NotePayload) -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "INSERT INTO spec_notes (spec_id, note) VALUES (:spec_id, :note)"
            ),
            {"spec_id": payload.spec_id, "note": payload.note},
        )
        await session.commit()
    return {"status": "ok"}


@router.get("/spec/notes/{spec_id}")
async def get_spec_notes(spec_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id, note, created_at FROM spec_notes WHERE spec_id = :sid ORDER BY created_at DESC"),
            {"sid": spec_id},
        )
        rows = result.fetchall()
    return {"notes": [{"id": r[0], "note": r[1], "created_at": str(r[2])} for r in rows]}
