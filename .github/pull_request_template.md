## Linked Issue
Closes #<!-- issue number required -->

## Pre-code checklist (must be done BEFORE writing implementation)
- [ ] GitHub issue exists with AC written in GIVEN/THEN format
- [ ] Test stubs committed on this branch (failing, referencing AC numbers)
- [ ] No implementation code exists yet when test stubs were first committed

## Implementation checklist
- [ ] All test functions reference AC number in name (e.g. `test_fire_AC1`)
- [ ] Each AC has at least one fire case test and one anti-case test
- [ ] No `assert True` or bare `pass` in test bodies
- [ ] Detail dict fields in output match fields specified in issue AC

## CI checklist (must be green before requesting review)
- [ ] pytest passing (300+ tests, 0 failures)
- [ ] Coverage ≥ 75%
- [ ] Playwright UI tests passing
- [ ] Trivial test check passing
- [ ] CI artifacts uploaded (junit.xml, playwright-report, screenshots)

## Evidence
<!-- paste link to CI run or screenshot showing green -->
