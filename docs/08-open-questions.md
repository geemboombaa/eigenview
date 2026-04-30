# 08 — Open Questions

**All blocking questions resolved as of 2026-04-24.** See `07-decisions.md` for answers. Phase 0 can start.

---

## Resolved (moved to decisions log)

- ✅ Q1 Starting universe — **S&P 500 + Nasdaq-100 (~540 tickers, ~400 after liquidity gate)**
- ✅ Q2 Data budget — **Free tier v1; paid bootstrap in v1.1**
- ✅ Q3 Daily schedule — **08:00 ET pre-market**
- ✅ Q4 Alert channels — **Dashboard + Windows desktop toast (default); other channels v2**

## One item to confirm before Phase 1

**Interpretation of "Nasdaq":** assumed to mean **Nasdaq-100** (top 100 by market cap, all very liquid options). NOT Nasdaq Composite (3000+ names, many illiquid).

If you meant Nasdaq Composite or a different subset (e.g. Nasdaq-100 + a handful of favorites), flag this when you open Claude Code for Phase 0.

---

## Non-blocking — can decide later

### Q5 — GitHub hosting

Public repo, private repo, or local-only Git? Default: **private GitHub repo** for backup + version history. No blocker either way.

---

### Q6 — Anthropic API key

For LLM calls in production (thesis generation, chat, novelty filtering):
- Same Claude subscription if API access is included
- Separate Anthropic API credits if not

Resolve during Phase 4 (when LLM integration begins). Not blocking earlier phases.

---

### Q7 — Broker integration (future)

Manual trading v1; revisit at v2.

---

### Q8 — Existing data / code to migrate?

- Any existing watchlists?
- Past trade journal in a format we can import?
- Python scripts you've written?

If yes, show at start of Phase 0 and we integrate. Otherwise, fresh build.
