# EigenView

A curated daily options-idea dashboard for US liquid-options stocks. Fuses technical analysis, GEX / dealer positioning, options flow, **dormant long-dated bet activation** (novel), and novelty-weighted news sentiment into 3–5 ranked trade ideas per day.

## Why this exists

Every options tool today produces individual factors — GEX from SpotGamma, flow from Unusual Whales, sentiment from Alpha Vantage. No tool combines them into a curated read-set-go pick list with the dormant-bet activation layer.

## Core differentiators (vs. Tradytics / Unusual Whales / InsiderFinance / SpotGamma)

1. **Dormant-bet radar** — tracks large long-dated options opened 30–180 days ago that haven't played out, scored by an ML activation classifier
2. **TA + GEX as hard gates** — not filter toggles; if either fails, no pick
3. **LLM-generated thesis per pick** — readable "why this, why now, what kills it" on every idea
4. **Novelty-weighted sentiment** — LLM-embedding distance from rolling baseline, not raw news volume
5. **Curated 3–5 picks** — not a scanner with 200 rows to filter

## Quick start

```bash
# 1. Install uv
irm https://astral.sh/uv/install.ps1 | iex   # PowerShell
# or: curl -LsSf https://astral.sh/uv/install.sh | sh  # bash

# 2. Clone & setup
git clone <repo> eigenview
cd eigenview
uv venv
uv pip install -e ".[dev]"

# 3. Configure API keys
cp .env.example .env
# Edit .env with Alpha Vantage + Finnhub free-tier keys

# 4. First run
uv run python -m eigenview.cli daily-scan

# 5. Dashboard
uv run python -m eigenview.cli serve
# open http://localhost:8080
```

## Documentation

- [01 — Vision & differentiators](./docs/01-vision.md)
- [02 — Module catalog](./docs/02-modules.md)
- [03 — Factor specifications](./docs/03-factors.md)
- [04 — UI templates](./docs/04-templates.md)
- [05 — Architecture](./docs/05-architecture.md)
- [06 — Build plan](./docs/06-build-plan.md)
- [07 — Decisions log](./docs/07-decisions.md)
- [08 — Open questions (blocking)](./docs/08-open-questions.md)

See [CLAUDE.md](./CLAUDE.md) for Claude Code project instructions.
