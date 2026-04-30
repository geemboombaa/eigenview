# 12 — Engineering Standards

How code is written, tested, and committed in EigenView. Claude Code follows these without prompting.

---

## Python conventions

### Style

- **Formatter:** `ruff format` (Black-compatible). Run on save.
- **Linter:** `ruff check` with default rules + `select = ["E", "F", "I", "N", "UP", "B"]`.
- **Type hints:** mandatory on public functions. Use `from __future__ import annotations` at top of every file.
- **Docstrings:** Google style. Mandatory on public functions/classes. One-liners on private helpers OK.
- **Imports:** ruff-isorted. Stdlib · third-party · local. No wildcard imports.

### Project structure rules

- One responsibility per module. If a file > 300 lines, split it.
- All factor modules implement the same interface (`compute(ticker: str) -> FactorResult`).
- All API endpoints in `api/`, one router per resource.
- All LLM prompts in `llm/prompts/` as `.md` files (versioned, diff-able).

### Error handling

- Use specific exceptions, not bare `Exception`.
- Network/API calls wrapped in retry logic (`tenacity`) — exponential backoff, max 3 attempts.
- Never `except: pass` — log and re-raise or handle specifically.
- User-facing errors return structured JSON: `{"error": str, "code": str, "retryable": bool}`.

### Logging

- Use `structlog` for structured logging.
- Log at INFO for major events (scan start/end, picks generated), DEBUG for per-ticker, WARNING for retries, ERROR for failures.
- Never log secrets. Use `repr()` censoring on env-derived strings.
- Each daily scan emits a single summary log line at completion: tickers scanned, time, picks produced, cost.

### Configuration

- All config from `pydantic-settings`, sourced from `.env`.
- No hardcoded API keys, paths, or thresholds in code.
- Factor thresholds (e.g. dormant-bet 0.6 firing threshold) live in `config.py` so we can tune without code changes.

---

## Frontend conventions

### Module pattern

Every UI module is a single ES module file:

```javascript
// web/modules/pick-cards.js
export const id = 'pick-cards';
export const defaultSize = 'M';
export const supportedSizes = ['M', 'L', 'XL'];

export class PickCards {
  constructor(container, config, store) {
    this.container = container;
    this.config = config;
    this.store = store;
    this.unsubscribe = null;
  }

  async mount() { /* render, fetch, subscribe */ }
  unmount() { /* cleanup, remove listeners */ }
  resize(size) { /* re-render */ }
}
```

### CSS

- All design tokens from `web/design-tokens.css`. Never hardcode colors/spacing.
- Per-module CSS in `web/modules/<module-id>.css`. BEM-ish naming: `.module-name__element--modifier`.
- Theme-aware via `[data-theme="dark|light"]` selectors.
- Avoid frameworks. No Tailwind, no Bootstrap.

### State

- Single global store (vanilla JS — no Redux). Pub-sub via simple event emitter.
- Modules subscribe to keys they care about; emit events for user actions.
- No localStorage / sessionStorage — backend is source of truth (fits EigenView's data flow).

---

## Testing

### Framework

- Python: `pytest` + `pytest-asyncio` for async + `pytest-cov` for coverage.
- Frontend: `vitest` for module unit tests + Playwright for e2e (Phase 6+).

### Coverage targets

- Factors: **≥ 90%** line coverage (these are the brain of the product)
- Synthesis: **≥ 90%** line coverage
- API: **≥ 80%** line coverage
- LLM layer: **≥ 70%** (prompts harder to fully test)
- Frontend modules: **≥ 70%** by Phase 6

### Test patterns

- One test file per source file: `factors/technical.py` ↔ `tests/factors/test_technical.py`
- Fixtures in `tests/fixtures/` — canned chains, news, prices for deterministic testing
- Mark slow/network tests: `@pytest.mark.slow`, run separately in CI
- Snapshot test factor outputs for stability — `pytest-snapshot`

### Mandatory tests per factor

1. **Happy path** — known-good ticker fires correctly
2. **Edge: no data** — empty chain, no news → returns `firing=False`, no exception
3. **Edge: stale data** — data > 24h old → returns warning in narrative
4. **Edge: malformed input** — bad ticker, missing fields → graceful degradation
5. **Determinism** — same input twice → identical output

### Integration tests

- Daily scan end-to-end on 5-ticker fixture universe → top 3 picks must include known true positives
- LLM-dependent tests can mock with VCR-style cassettes (`pytest-vcr`)

---

## Git workflow

### Commits

- **Atomic** — one logical change per commit
- **Conventional Commits** format: `feat(factors): add dormant-bet rule-based scorer`
- Types: `feat | fix | docs | refactor | test | chore | perf | style`
- Scope: file or module name
- Body explains WHY, not what (the diff shows what)

### Branches

- `main` — always deployable
- `feat/<phase>-<thing>` — feature branches per build-plan phase
- No PR for solo build (commit to main is fine), but use branches if exploring

### Don'ts

- No commits with secrets — `git-secrets` or `pre-commit` hook to scan
- No commits with broken tests — `pre-commit` runs tests
- No `--force` push to main ever

---

## Pre-commit hooks (`.pre-commit-config.yaml`)

```yaml
- ruff check --fix
- ruff format
- pytest -q --tb=short -m "not slow"
- check for committed .env or secrets
- check that all new factor modules have a corresponding test file
```

---

## Documentation requirements

Every PR (or significant commit) must:
- Update `docs/07-decisions.md` if a non-obvious design decision was made
- Add/update docstring on any new public API
- Update `docs/02-modules.md` if a module's data contract changed
- Update `CLAUDE.md` if it changes how Claude should approach future sessions

Drift between code and docs is a bug.

---

## Performance budgets

- Daily scan total: **< 5 min** on 400-ticker universe (parallelized)
- Single ticker factor compute: **< 2s**
- Dashboard initial render: **< 2s** on cached data
- API endpoint p95 latency: **< 500ms**
- Chat first token: **< 1.5s**

If a change blows a budget, profile before merging.

---

## Security baseline

- No external network exposure in v1 (FastAPI binds 127.0.0.1)
- Secrets via `.env` only, `.env.example` committed with placeholders
- API keys rotated if accidentally leaked (document in `docs/07-decisions.md`)
- SQLite file in `data/` — gitignored
- Future deployment: TLS + auth required before exposing to internet
