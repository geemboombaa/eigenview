# Enforcement System — Requirements Spec

## Feature
W1-W4 enforcement: stop-gate, pre-build-gate, phase-aware pre-commit, verify-red-phase CI job, gate:awaiting-step21 label mechanism.

## Acceptance Criteria

### AC1 — stop-gate: dirty src/ blocks instantly
GIVEN a Claude turn ends
AND `git diff --name-only HEAD` shows at least one file under `src/`
THEN stop-gate output JSON has `decision = "block"`
AND reason text mentions "src/ file(s) changed but not committed"
AND block fires in under 10 seconds (no pytest run occurs)

### AC2 — stop-gate: clean src/ + passing tests → allow
GIVEN a Claude turn ends
AND `git diff --name-only HEAD` shows no files under `src/`
AND all tests in the project pass
THEN stop-gate does not output a block decision
AND exit code is 0

### AC3 — stop-gate: clean src/ + failing tests → block
GIVEN a Claude turn ends
AND `git diff --name-only HEAD` shows no files under `src/`
AND at least one test fails
THEN stop-gate output JSON has `decision = "block"`
AND reason text contains test failure output

### AC4 — pre-build-gate: master branch blocks all writes
GIVEN tool_name is "Write" or "Edit"
AND current git branch is "master" or "main"
WHEN pre-build-gate fires
THEN output JSON has `decision = "block"`
AND reason mentions the branch name

### AC5 — pre-build-gate: no open PR blocks
GIVEN tool_name is "Write" or "Edit"
AND current branch is not master/main
AND `gh pr list --head <branch> --state open` returns 0 results
WHEN pre-build-gate fires
THEN output JSON has `decision = "block"`
AND reason mentions "no open PR"

### AC6 — pre-build-gate: gate:awaiting-step21 on feature/ blocks
GIVEN tool_name is "Write" or "Edit"
AND current branch starts with "feature/"
AND an open PR exists for the branch
AND the PR has label "gate:awaiting-step21"
WHEN pre-build-gate fires
THEN output JSON has `decision = "block"`
AND reason mentions "gate:awaiting-step21"

### AC7 — pre-build-gate: fix/ branch bypasses gate label
GIVEN tool_name is "Write" or "Edit"
AND current branch starts with "fix/"
AND an open PR exists for the branch
AND the PR has label "gate:awaiting-step21"
WHEN pre-build-gate fires
THEN output does NOT have `decision = "block"` (allow)

### AC8 — pre-build-gate: .boss/ writes always allowed
GIVEN tool_name is "Write" or "Edit"
AND file_path resolves inside the `.boss/` directory
AND current branch is "master"
WHEN pre-build-gate fires
THEN output does NOT have `decision = "block"` (allow)

### AC9 — pre-commit RED phase: stubs fail + no regression → allow commit
GIVEN only `tests/` files are staged (no `src/` staged)
AND new test stub files are staged (--diff-filter=A)
AND existing tests pass when stubs are excluded
AND new stub tests fail (non-zero pytest exit on stub files)
WHEN pre-commit hook executes
THEN exit code is 0 (commit allowed)

### AC10 — pre-commit RED phase: existing test regression → block commit
GIVEN only `tests/` files are staged
AND at least one existing (non-stub) test fails
WHEN pre-commit hook executes
THEN exit code is 1 (commit blocked)
AND output contains "COMMIT BLOCKED: existing tests regressed"

### AC11 — pre-commit RED phase: stubs pass → block commit
GIVEN only `tests/` files are staged
AND new stub tests are staged
AND stub tests pass (implementation already exists)
WHEN pre-commit hook executes
THEN exit code is 1 (commit blocked)
AND output contains "COMMIT BLOCKED: stubs PASSED"

### AC12 — pre-commit GREEN phase: all tests pass → allow commit
GIVEN `src/` files are staged
AND all tests pass
WHEN pre-commit hook executes
THEN exit code is 0 (commit allowed)

### AC13 — pre-commit GREEN phase: any test fails → block commit
GIVEN `src/` files are staged
AND at least one test fails
WHEN pre-commit hook executes
THEN exit code is 1 (commit blocked)
AND output contains "COMMIT BLOCKED: tests failed"

### AC14 — pre-commit DOCS phase: no src/ no tests/ → regression check only
GIVEN no `src/` files are staged
AND no `tests/` files are staged
AND existing tests pass
WHEN pre-commit hook executes
THEN exit code is 0 (commit allowed)
AND output contains "docs-only commit"

## Out of Scope
- Testing verify-red-phase CI job (requires GitHub Actions environment)
- Testing auto-push hook (requires real remote)
- Testing gate:awaiting-step21 label creation (requires GitHub API credentials)

## Dependencies
- `.git/hooks/pre-commit` — bash script, tested via subprocess in temp git repos
- `~/.claude/boss/hooks/pre-build-gate.ps1` — PowerShell, tested via subprocess with mock JSON payloads
- `~/.claude/boss/hooks/stop-gate.ps1` — PowerShell, tested via subprocess with mock JSON payloads
