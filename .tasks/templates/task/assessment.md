# Assessment

## Status

- Task: `__REQUIRED_TASK_ID__`
- Assessment state: In progress
- Repository default branch: `[branch]`
- Assessed base commit: `[SHA]`
- Assessment timestamp: `[ISO-8601 timestamp]`
- Initial working-tree status: `[clean or summarized changes]`

Record the base commit and timestamp in `task.yaml` under `assessment`.

## Assessment objective

Explain what must be understood before selecting an implementation approach.

## Repository baseline

Summarize relevant architecture, runtime boundaries, data flow, and current behavior.

## Files inspected

| Path | Symbols or line ranges | Why inspected | Relevant observation |
|---|---|---|---|
| `[path]` | `[symbol or lines]` | [Reason] | [Observation] |

## Repository commands run

Record consequential commands only.

| Command | Purpose | Result | Effect on assessment |
|---|---|---|---|
| `[command]` | [Purpose] | [Result] | [Impact] |

## Current behavior

Describe the observed current state. For bugs, include reproduction steps and actual results.

## Expected behavior

Describe the intended outcome without choosing an implementation prematurely.

## Important code locations

| Location | Responsibility | Relevance |
|---|---|---|
| `[path:symbol]` | [Responsibility] | [Why it matters] |

## Existing tests and validation paths

- [Test suite, fixture, command, workflow, or manual validation path]

## Constraints discovered

- [Constraint]

## Assumptions

- [Assumption and why it is reasonable]

## Risks

| Risk | Likelihood | Impact | Initial mitigation |
|---|---|---|---|
| [Risk] | [Low/Medium/High] | [Low/Medium/High] | [Mitigation] |

## Unknowns and questions

- [Unknown research or findings must resolve]

## Base-drift recheck

Complete immediately before branch creation.

- Current default-branch commit: `[SHA]`
- Changes since assessed commit: `[summary or None]`
- Task-relevant drift: `[Yes/No]`
- Action: `[Continue / refresh assessment / invalidate approval]`

## Not applicable sections

List any standard assessment area that does not apply and explain why.
