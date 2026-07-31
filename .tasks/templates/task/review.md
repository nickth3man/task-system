# Same-Agent Review

## Record

- Task: `__REQUIRED_TASK_ID__`
- Base commit: `[SHA]`
- Reviewed committed head: `[SHA]`
- Reviewer: Implementing agent
- Review status: In progress

## Candidate-state safety

- Staged changes after candidate commit: `[None or details]`
- Unstaged changes after candidate commit: `[None or details]`
- Untracked files after candidate commit: `[None or details]`

## Committed diff reviewed

- Stat command: `[configured diff_base command]`
- Full command: `[configured diff_full command]`
- Files changed: `[count]`
- Additions/deletions: `[values]`

The review target must be the committed head. Do not use `base...HEAD` while implementation remains uncommitted.

## Scope conformance

- Implements only the approved task and plan: `[Yes/No]`
- Unrelated or accidental changes: `[None or details]`
- Material deviations: `[None or approval reference]`

## Acceptance-criterion review

| Criterion | Implementation present | Verification present | Review result |
|---|---|---|---|
| AC-01 | [Yes/No] | [Yes/No] | [Pass/Fail] |

## Code and architecture review

- Correctness: [Finding]
- Error handling: [Finding]
- Maintainability: [Finding]
- Repository-pattern consistency: [Finding]
- Performance: [Finding or Not applicable]
- Security and privacy: [Finding or Not applicable]
- Compatibility and migration: [Finding or Not applicable]

## Tests and validation review

- Changed-behavior coverage: [Finding]
- Regression coverage: [Finding]
- Flakiness/environment risk: [Finding]
- Skipped checks: [Finding]

## Dependencies, generated files, and data changes

- Dependency changes: [Finding or Not applicable]
- Lockfile changes: [Finding or Not applicable]
- Generated artifacts: [Finding or Not applicable]
- Database/schema changes: [Finding or Not applicable]

## Documentation review

- User-facing documentation: [Finding or Not applicable]
- Developer documentation: [Finding or Not applicable]
- Task artifacts accurately reflect implementation: [Yes/No]

## Review findings and resolutions

| ID | Severity | Finding | Resolution | Status |
|---|---|---|---|---|
| REV-01 | [Critical/High/Medium/Low] | [Finding] | [Fix or rationale] | [Open/Resolved] |

When changes are required, return to `implementing`, then repeat testing, committing, and review for the new head.

## Remaining risks

- [Risk]

## Final review verdict

Choose one:

- Approved for push
- Changes required
- Blocked

Explain the verdict.
