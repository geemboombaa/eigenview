# BOSS — Build Orchestration System for Software
# A Claude Code enforcement layer for TDD + independent AI audit on every PR

## What is BOSS?

BOSS is a set of git hooks + GitHub Actions workflows that enforce a structured
build process on every PR. It works with Claude Code (or any AI coding agent) to:

1. Block implementation until a spec and test stubs exist
2. Run an independent AI audit with zero context from the builder
3. Require human review before implementation begins
4. Enforce red-green TDD phases at commit time
5. Post BOSS_FIX_REQUEST / BOSS_YELLOW_FLAGS / BOSS_ESCALATE comments for the AI agent to self-heal

## Core Properties

- **Asymmetric verification:** The audit agent (CI) reads only spec + test names. It cannot
  see the builder's implementation. Like a code review from someone who reads the spec first.
- **Mechanical enforcement:** Pre-commit hook enforces red/green phases. You cannot commit
  green code in the red phase. You cannot commit failing tests in the green phase.
- **Label-gated implementation:** CI sets `gate:awaiting-step21` after red phase.
  Only a human can remove it (GitHub UI). This is the approval gate.
- **BOSS mechanism:** CI auto-posts structured comments. Claude Code reads them next session
  and self-heals. Up to 3 attempts. Then escalates to human.

## Files to copy into your project

```
.boss/
  PROCESS-TEMPLATE.md        ← copy to CURRENT-STEP.md for each feature
  BOSS-README.md             ← this file

.github/workflows/
  ac-audit.yml               ← zero-context Claude AI audit on every push
  test.yml                   ← full pytest + coverage + Playwright
  integration-live.yml       ← nightly live data E2E (optional, requires live data)

.git/hooks/ (or hooks/ symlinked to .git/hooks/)
  pre-commit                 ← red/green phase enforcement
  stop-gate.ps1              ← blocks if src/ dirty before tests
  pre-build-gate.ps1         ← blocks src/ writes unless PR open + no gate label

docs/
  chat-tracker.html          ← session-spanning ask tracker (optional but recommended)
```

## Setup Steps (new project)

1. Copy `.boss/`, `.github/workflows/ac-audit.yml`, `hooks/` into your project
2. Symlink hooks: `git config core.hooksPath hooks`
3. Set GitHub secrets: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` (auto-provided)
4. Add branch protection: require CI green + 1 approval before merge
5. Create labels in GitHub: `gate:awaiting-step21`, `phase:red`, `phase:green`,
   `status:ci-failing`, `status:yellow-flags-pending`, `status:needs-human-debug`
6. In `CLAUDE.md`, add the 29-step process reference (or paste the table from PROCESS-TEMPLATE.md)

## Adapting to your stack

The hooks are PowerShell-first (Windows) but Bash equivalents are straightforward.

**To change test runner:** edit `pre-commit` line that calls pytest. Replace with your runner.

**To change CI platform:** ac-audit.yml is GitHub Actions. The audit logic
(`audit_ac_coverage.py`) is pure Python and runs anywhere.

**To remove Windows dependency:** hooks use `pwsh` for the gate scripts.
Replace with bash equivalents (~10 lines each).

## Learnings from EigenView (what to get right from day 1)

### Gate path scope — CRITICAL
`gate:awaiting-step21` must only block `src/` and `tests/`, NOT `docs/`, `.boss/`, config files.
The design review (step 20) writes docs. If gate blocks docs, designer is stuck in a loop
requiring manual label removal just to write docs. Make gate path-aware:

```powershell
$isImplementationPath = $false
if ($filePath) {
    $abs = [System.IO.Path]::GetFullPath($filePath)
    if ($abs.StartsWith($srcDir) -or $abs.StartsWith($testsDir)) {
        $isImplementationPath = $true
    }
}
if ($isImplementationPath) { # ... check label }
```

### AC traceability: scan only changed files, not all tests
If you scan all test files for AC references, you'll find 300+ noise hits in any real codebase.
Use `git diff HEAD^1 HEAD --name-only` to get only files changed in this push, then scan those.

### Step trigger comment: be explicit about step number
The CI comment that tells Claude "next step is X" must reference the actual step number
(e.g., "Step 20") not a generic message. Claude reads this comment cold at session start.

### No synthetic data in integration tests
If your product has live data (APIs, DBs), do not create synthetic fixtures for integration tests.
Synthetic fixtures test the fixture, not the integration. Use real API calls + real DB.
Mark tests that need real data as `@pytest.mark.data_dependent` so they become YELLOW flags
(non-blocking) rather than RED failures when data is unavailable.

### NotImplementedError stubs must be closed before green phase
Pre-commit in green phase should count `NotImplementedError` in staged test files and
block if count > 0. Otherwise stubs silently pass through to "done" claims.
Add this check:

```bash
ni_count=$(grep -rn "NotImplementedError" tests/ --include="*.py" | wc -l)
if [ "$ni_count" -gt "0" ]; then
    echo "ERROR: $ni_count NotImplementedError stubs remain in tests/. Close them."
    exit 1
fi
```

### Playwright conftest: check server already running before starting
If CI or a developer already has the server running, the fixture should detect it
and reuse it rather than fail or start a second instance.

## Honest Assessment: is 29 steps optimal?

**No.** The current design conflates CI mechanics with process steps.
Steps 13-18 are all "CI runs one thing" — they're implementation details of one trigger.

**Recommended structure for v2:**

| Phase | Steps | Description |
|-------|-------|-------------|
| Proposal | 1-4 | Requirement → spec → human approve (1 gate) |
| Stub | 5-8 | spec.md + stubs + PR — mechanical enforcement starts |
| Audit | 9 | CI runs: red phase check + AI audit + gate set (1 step, not 6) |
| Design gate | 10 | Human approves audit → removes gate (1 gate) |
| Implement | 11 | Code + green phase commits |
| Ship gate | 12-13 | Human review + human merge (2 gates, 1 CI re-run) |

**6 human-visible phases, 2 human gates (not 4).** The mechanical steps (hooks, CI jobs)
are internal to each phase — not surfaced to the process owner.

## Open source checklist

- [ ] Remove eigenview-specific paths from hooks (make configurable via .boss/config.yml)
- [ ] Replace hardcoded `ANTHROPIC_API_KEY` env var name with configurable
- [ ] Replace hardcoded `origin/master` with auto-detected default branch
- [ ] Extract `audit_ac_coverage.py` from ac-audit.yml inline script → standalone file
- [ ] Add `bootstrap.sh` / `bootstrap.ps1` that installs all hooks + creates labels
- [ ] Write `docs/BOSS-QUICKSTART.md` (setup in 15 minutes)
- [ ] Test on a clean project (no eigenview imports)
- [ ] Publish as GitHub template repo: `geemboombaa/boss`
