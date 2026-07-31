# Completion Record

## Final outcome

Summarize what was delivered and whether the independently mergeable objective was achieved.

## Task metadata

- Task: `__REQUIRED_TASK_ID__ — __REQUIRED_TASK_TITLE__`
- Final task-system version: `2.0.0`
- Implementation status: `completed`
- Archive status: `[not_started/preparing/pr_open/archived]`
- Base branch: `[branch]`
- Task branch: `[branch]`
- Started: `[timestamp]`
- Implementation PR merged: `[timestamp]`

## Implementation pull request and merge

- Implementation PR: `[number and URL]`
- PR head SHA approved for merge: `[SHA]`
- Required checks: `[summary]`
- Merge strategy: `[repository policy/squash/merge/rebase]`
- Implementation merge commit: `[SHA]`
- Merged by: `[actor]`

## Commits

| SHA | Subject | Purpose |
|---|---|---|
| `[SHA]` | `__REQUIRED_TASK_ID__: [subject]` | [Purpose] |

## Acceptance criteria

| Criterion | Final status | Evidence |
|---|---|---|
| AC-01 | Passed | [Verification section, test, metric, screenshot, or commit] |

## Implementation summary

Describe durable technical changes for future maintainers.

## Plan deviations and approvals

- [Minor deviation and rationale]
- [Material revision and approval reference, or None]

## Testing and workflow checks

| Check | Result | Evidence |
|---|---|---|
| [Local command or GitHub workflow] | [Passed/Failed/Skipped] | [URL, log, or verification section] |

## Before/after metrics

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| [Metric] | [Value] | [Value] | [Meaning] |

If metrics do not apply, explain why.

## Screenshots retained

| Path | What it proves |
|---|---|
| `evidence/screenshots/[file]` | [Purpose] |

## Remaining risks

- [Risk or None]

## Known failures

- [Failure or None]

## Skipped checks

- [Check and reason, or None]

## Follow-up work outside scope

- [Potential separate task, or None]

## Condensed implementation history

Preserve important discoveries, decisions, failures, and resolutions from `implementation-log.md`. Remove redundant chronological noise before archival.

## Archive preparation

- Archive path: `.tasks/archive/[YYYY]/[MM]/__REQUIRED_TASK_ID__-__REQUIRED_SLUG__/`
- Authorization: inherited from implementation merge approval for head `[SHA]`
- Archival PR: `[number and URL]`
- Archival branch/head SHA: `[branch @ SHA]`
- Archival PR checks: `[summary]`
- Temporary evidence removed: `[summary]`
- Index regenerated: `[Yes/No]`

The archival record intentionally does not contain the archival PR's own merge SHA or merge timestamp. Presence of this task directory under `.tasks/archive/` on the default branch is authoritative proof that archival completed.
