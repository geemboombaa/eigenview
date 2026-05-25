# Integration E2E Suite — Requirements Spec

## Feature
integration-e2e-suite: live nightly integration CI, A-Z condition coverage tests,
Suite A Playwright functional, Suite B Playwright data validation, BOSS auto-fix
mechanism, pre-commit enforcement of integration test presence.

## Acceptance Criteria

### AC1 — integration-live.yml: nightly cron + manual dispatch trigger
GIVEN `.github/workflows/integration-live.yml` exists
THEN it has a `schedule:` trigger with a cron expression
AND it has a `workflow_dispatch:` trigger
AND the schedule fires at a time that allows markets to close (post-market)

### AC2 — workflow uses real API secrets, not placeholders
GIVEN the integration-live.yml workflow runs
THEN it reads `ALPHA_VANTAGE_KEY`, `FINNHUB_KEY` from `secrets.*`
AND it does NOT contain the string "placeholder" in any env var value
AND it fails fast with a clear message if secrets are absent

### AC3 — NEVER_FIRED detection: fails when a required pattern is absent
GIVEN a scan output JSON where `pullback_in_trend` fired 0 times across all scanned tickers
WHEN the condition_coverage checker runs against that output
THEN it reports `pullback_in_trend: NEVER_FIRED`
AND exits with a non-zero code

### AC4 — condition_coverage passes when all required patterns fire
GIVEN a scan output JSON where every required TA pattern fires at least once
WHEN the condition_coverage checker runs
THEN all rows show FIRED
AND exits with code 0

### AC5 — YELLOW flag: data_dependent test failure posts BOSS_YELLOW_FLAGS to PR
GIVEN a CI run where a test marked `@pytest.mark.data_dependent` fails
WHEN the integration-live.yml post-run step executes
THEN a comment is posted to the PR containing `BOSS_YELLOW_FLAGS`
AND the label `status:yellow-flags-pending` is set on the PR (via GITHUB_TOKEN)
AND the build is NOT marked as failed

### AC6 — RED failure: BOSS_FIX_REQUEST posted + status:ci-failing set
GIVEN a CI run where a test WITHOUT `@pytest.mark.data_dependent` fails
WHEN the integration-live.yml post-run step executes
THEN a comment containing `BOSS_FIX_REQUEST` JSON is posted to the PR
AND the label `status:ci-failing` is set on the PR (via GITHUB_TOKEN)
AND the build IS marked as failed (non-zero exit)

### AC7 — 3 consecutive RED failures sets status:needs-human-debug
GIVEN the BOSS_FIX_REQUEST comment contains `"attempt": 3`
AND the CI run still fails after that attempt
THEN the label `status:needs-human-debug` is set
AND the label `status:ci-failing` is removed
AND the comment body contains `BOSS_ESCALATE`

### AC8 — Suite A Playwright: all UI functional paths covered
GIVEN the server is running with mocked API responses
WHEN Suite A Playwright tests run (`tests/ui/functional/`)
THEN tests exist and execute for:
  - 4 themes (dark, light, glass, bento) with CSS var verification
  - 5 templates (STANDARD, MINIMAL, PRO, RESEARCH, FOCUS) with 1-5 key binding
  - Keyboard shortcuts: Ctrl+K, /, E, ?, H, arrow navigation
  - Favorites: pin card → appears in Mine tab → persists localStorage
  - Edit mode: drag, resize, close, color palette
  - Category nav: filter by setup type
  - Factor strip: collapse/expand, dot click opens detail panel
  - Help page: all 11 tabs render
AND all tests pass

### AC9 — Suite B Playwright: pick card UI fields match DB values
GIVEN the server is running with real picks in DB from fixture scan
WHEN Suite B Playwright data validation tests run (`tests/ui/data/`)
THEN for each pick card rendered:
  - ticker text = DB pick.ticker
  - conviction dot count = DB pick.conviction (integer)
  - entry zone text = formatted DB pick.entry_low / pick.entry_high
  - stop text = formatted DB pick.stop
  - direction badge text = DB pick.direction
  - factor strip dots: green = factors_json.{factor}.firing == True, gray = False
AND all fields match with zero mismatches

### AC10 — integration-live.yml uploads artifacts after every run
GIVEN integration-live.yml completes (pass or fail)
THEN GitHub Actions artifacts include:
  - `playwright-report/` (HTML report with screenshots)
  - `condition-coverage.json` (FIRED/NEVER_FIRED for all required patterns)
  - `results/junit-integration.xml` (pytest results)
AND artifacts are retained for 30 days

### AC11 — pre-commit GREEN: blocks if src/ changed but no integration + playwright tests added
GIVEN files under `src/` are staged for commit
AND no new file is staged under `tests/integration/`
AND no new file is staged under `tests/ui/`
WHEN the pre-commit GREEN phase runs
THEN exit code is 1
AND output contains "COMMIT BLOCKED: src/ change requires integration test"

## Out of Scope
- Running integration-live against full S&P 500 (NDX100 subset = 100 stocks, sufficient)
- Storing historical scan results long-term (DB cleared between nightly runs)
- Playwright video recording (screenshots only in v1)
- The synthetic fixture approach (deferred — see GitHub issue #123)

## Dependencies
- `.github/workflows/integration-live.yml` — new workflow
- `tests/integration/test_condition_coverage.py` — NEVER_FIRED checker
- `tests/integration/test_api_full.py` — field-by-field API validation
- `tests/integration/test_scan_e2e.py` — full scanner A-Z
- `tests/ui/functional/` — Suite A (new directory)
- `tests/ui/data/` — Suite B (new directory)
- `.git/hooks/pre-commit` — GREEN phase updated with integration test check
- `conftest.py` — `data_dependent` pytest marker registration
- GitHub Secrets: `ALPHA_VANTAGE_KEY`, `FINNHUB_KEY`, `ANTHROPIC_API_KEY`
