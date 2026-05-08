# Design Review — integration-e2e-suite
# Step 20 of 29-step process

## Feature
integration-e2e-suite (PR #125, Issue #124)

## Do I Have Everything for A-Z Implementation?

### AC1 — Nightly integration workflow (integration-live.yml)
**Have:**
- Workflow trigger spec (post-market schedule + manual dispatch)
- Required secrets list (ALPHA_VANTAGE_KEY, FINNHUB_KEY, ANTHROPIC_API_KEY, real DB)
- Test stubs in tests/integration/test_workflow_structure_ac1_ac2.py

**Gap:**
- Need to decide: does integration-live.yml live in .github/workflows/ on this branch or master?
- Answer: this branch — ac-audit.yml proved this pattern works

### AC2 — Real secrets, no placeholders
**Have:** Stubs that verify env vars are set and non-placeholder
**Gap:** None — straightforward env var checks in CI

### AC3 — NEVER_FIRED condition detection
**Have:** Stubs in test_condition_coverage_ac3_ac4.py
**Gap:** Need to write condition_coverage.py script that:
  - Imports all 21 setup names from technical.py
  - Reads signal_triggers table for last N days
  - Flags any setup_type with zero occurrences = NEVER_FIRED

### AC4 — All patterns fire in controlled env
**Have:** Stubs
**Gap:** Need fixture data that guarantees each of 21 setups fires (synthetic OHLCV). This is the hard part. Options:
  1. Synthetic OHLCV generator per setup (purest)
  2. Historical cassettes from real data that are known to fire each setup
  Decision: Synthetic — not dependent on live data

### AC5/AC6/AC7 — BOSS mechanism (YELLOW/RED/escalation)
**Have:** Stubs in test_boss_mechanism_ac5_ac6_ac7.py
**Gap:** Need to implement:
  - CI job that reads pytest result XML
  - Maps data_dependent failures → BOSS_YELLOW_FLAGS comment
  - Maps hard failures → BOSS_FIX_REQUEST comment + status:ci-failing label
  - 3-strike counter (stored in PR labels or file)

### AC8 — Suite A Playwright (functional UI)
**Have:** 24 stubs in tests/ui/functional/test_suite_a_ac8.py
**Gap:** Need:
  - pytest-playwright fixture with mocked API responses
  - Server startup fixture (uvicorn in subprocess)
  - Mock API layer (httpretty or pytest-httpserver)

### AC9 — Suite B Playwright (data validation)
**Have:** 12 stubs in tests/ui/data/test_suite_b_ac9_ac10.py
**Gap:** Need:
  - Real DB fixture with known picks
  - Server running against that DB
  - Field-by-field comparison logic

### AC10 — Artifact uploads
**Have:** Stubs checking workflow YAML for upload-artifact steps
**Gap:** These are workflow YAML checks — can be implemented as simple file reads + assertions, no live CI needed

### AC11 — Pre-commit GREEN phase integration check
**Have:** 6 stubs in tests/integration/test_precommit_enforcement_ac11.py
**Gap:** Need subprocess-based test that actually runs the pre-commit hook — goes in tests/integration/enforcement/

## Gaps Summary

| AC | Gap | Effort |
|----|-----|--------|
| AC1 | Write integration-live.yml | Medium |
| AC3 | Write condition_coverage.py | Small |
| AC4 | Synthetic OHLCV per setup | Hard |
| AC5-7 | BOSS comment/label mechanism in CI | Medium |
| AC8 | Playwright fixture + mock server | Hard |
| AC9 | Real DB fixture for UI tests | Medium |
| AC10 | Workflow YAML assertion tests | Small |
| AC11 | subprocess pre-commit tests | Small |

## Files to Create in Green Phase

```
.github/workflows/integration-live.yml
src/eigenview/ci/condition_coverage.py
src/eigenview/ci/boss_mechanism.py
tests/integration/test_workflow_structure_ac1_ac2.py   (replace stubs)
tests/integration/test_condition_coverage_ac3_ac4.py   (replace stubs)
tests/integration/test_boss_mechanism_ac5_ac6_ac7.py   (replace stubs)
tests/integration/test_precommit_enforcement_ac11.py   (replace stubs)
tests/ui/functional/test_suite_a_ac8.py                (replace stubs)
tests/ui/data/test_suite_b_ac9_ac10.py                 (replace stubs)
tests/fixtures/synthetic_ohlcv/                        (per-setup fixtures)
tests/ui/conftest.py                                   (Playwright fixtures)
```

## Parallel Workstream Note

The Opus 4.7 intelligent layer design (docs/intelligent-layer-design.md) is ready.
It does NOT conflict with this feature — intelligent layer touches synthesis/ and config/,
this feature touches CI + tests. Both can proceed in parallel after step 21 unlocks src/.

## Decision Required from Human at Step 21

After removing gate:awaiting-step21 label, confirm priority order:
A) Implement integration-e2e-suite (AC1-AC11) first, THEN intelligent layer
B) Implement intelligent layer (config/strategy.yaml + FeatureVector + scorer) first, THEN integration suite
C) Both in parallel on separate branches

Recommendation: A — integration infrastructure first. Intelligent layer needs the forward_returns
table which becomes meaningful only when real scans are running and validated.
