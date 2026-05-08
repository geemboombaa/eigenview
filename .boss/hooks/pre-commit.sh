#!/bin/sh
# pre-commit: red/green phase-aware test gate
#
# RED PHASE  (only tests/ staged, no src/):
#   - Existing tests MUST PASS  (no regressions)
#   - Staged new stub tests MUST FAIL (no implementation yet)
#   - Block if stubs somehow PASS (implementation already exists = wrong phase)
#
# GREEN PHASE (src/ files staged):
#   - ALL tests MUST PASS
#   - Block on any failure
#
# DOCS PHASE (.boss/ .github/ web/ only — no src/ no tests/):
#   - Existing tests MUST PASS

VENV_PYTHON=".venv/Scripts/python.exe"
if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON=".venv/bin/python"
fi
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: no venv python at .venv/Scripts/python.exe or .venv/bin/python"
    exit 1
fi

STAGED_SRC=$(git diff --cached --name-only | grep -E "^src/" || true)
STAGED_TESTS=$(git diff --cached --name-only | grep -E "^tests/.*\.py$" || true)
STAGED_NEW_TESTS=$(git diff --cached --name-only --diff-filter=A | grep -E "^tests/.*\.py$" || true)

# ── Docs-only (.boss/ .github/ web/ etc) ──────────────────────────────────────
if [ -z "$STAGED_SRC" ] && [ -z "$STAGED_TESTS" ]; then
    echo "[pre-commit] docs-only commit — regression check..."
    "$VENV_PYTHON" -m pytest -q --tb=short --no-header --maxfail=5 \
        --ignore=tests/integration --ignore=tests/ui
    if [ $? -ne 0 ]; then
        echo "COMMIT BLOCKED: existing tests regressed"
        exit 1
    fi
    echo "Tests pass. Docs commit allowed."
    exit 0
fi

# ── RED PHASE: only tests/ staged ────────────────────────────────────────────
if [ -z "$STAGED_SRC" ] && [ -n "$STAGED_TESTS" ]; then
    echo "[pre-commit] RED PHASE — only tests/ staged"

    # Build --ignore args for each new stub file
    IGNORE_ARGS=""
    for f in $STAGED_NEW_TESTS; do
        IGNORE_ARGS="$IGNORE_ARGS --ignore=$f"
    done

    echo "  1/2 regression check (existing tests, ignoring new stubs)..."
    "$VENV_PYTHON" -m pytest -q --tb=short --no-header --maxfail=5 \
        --ignore=tests/integration --ignore=tests/ui $IGNORE_ARGS
    if [ $? -ne 0 ]; then
        echo "COMMIT BLOCKED: existing tests regressed"
        exit 1
    fi
    echo "  OK: no regressions"

    if [ -n "$STAGED_NEW_TESTS" ]; then
        echo "  2/2 stub verification (must FAIL)..."
        "$VENV_PYTHON" -m pytest -q --tb=line --no-header $STAGED_NEW_TESTS 2>&1
        STUB_EXIT=$?
        if [ $STUB_EXIT -eq 0 ]; then
            echo ""
            echo "COMMIT BLOCKED: stubs PASSED — red phase violation."
            echo "Stubs must fail here. No implementation should exist yet."
            exit 1
        fi
        echo "  OK: stubs fail as expected (red phase correct)"
    fi

    echo "Red phase commit allowed."
    exit 0
fi

# ── GREEN PHASE: src/ files staged ───────────────────────────────────────────
if [ -n "$STAGED_SRC" ]; then
    echo "[pre-commit] GREEN PHASE — src/ staged, running full suite..."
    "$VENV_PYTHON" -m pytest -q --tb=short --no-header --maxfail=5 \
        --ignore=tests/integration --ignore=tests/ui
    if [ $? -ne 0 ]; then
        echo "COMMIT BLOCKED: tests failed. Green phase requires all tests pass."
        exit 1
    fi
    echo "All tests pass. Green phase commit allowed."
    exit 0
fi

exit 0
