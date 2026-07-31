# Task Lifecycle Instructions for Agents

These instructions govern all work recorded under `.tasks/`. Repository development rules remain in the root `AGENTS.md`. Both files apply.

## 1. Non-negotiable principles

1. One independently mergeable feature or bug fix equals one task directory.
2. One agent owns the task from intake through merge and archival.
3. `task.yaml` is the authoritative state record.
4. Markdown artifacts preserve reasoning, evidence, decisions, and outcomes without duplicating one another wholesale.
5. Every required stage is entered. Use `Not applicable` with a reason instead of silently skipping work.
6. No production source changes occur before plan approval and branch creation.
7. The agent never silently stashes, discards, overwrites, commits, or incorporates unrelated user work.
8. User approval in chat is required for findings, plan, PR creation, and merge.
9. A task is complete only after the implementation PR is merged, final records are written, and the mechanical archival PR is merged.
10. Do not wait for review comments unless the user explicitly requests that behavior. GitHub workflow checks are the required post-PR gate.

## 2. Supported task types

Use the full lifecycle for feature implementation, bug fixes, refactors, performance improvements, security remediation, project audits, research-only tasks, documentation, dependency upgrades, data or database work, UI/UX improvements, repository setup or scaffolding, and other independently mergeable repository work.

All task types use the same files. A section may be marked `Not applicable` only with a concrete reason.

## 3. Directory and identifier rules

Active task path:

```text
.tasks/active/TASK-YYYY-NNN-kebab-case-slug/
```

Archive path:

```text
.tasks/archive/YYYY/MM/TASK-YYYY-NNN-kebab-case-slug/
```

Identifiers are sequential per repository and year. Scan every `task.yaml` under `.tasks/active/` and `.tasks/archive/`, find the highest sequence for the current year, add one, and format it with three digits. Do not rely only on `.tasks/index.yaml`. Stop and resolve duplicate IDs.

Default branch name:

```text
task/TASK-YYYY-NNN-kebab-case-slug
```

## 4. Required artifacts and ownership

| Artifact | Sole primary responsibility |
|---|---|
| `task.yaml` | Machine-readable task state, approvals, revisions, acceptance-status references, Git/PR/merge metadata |
| `task.md` | Original request, objective, scope, constraints, non-goals, acceptance-criterion text |
| `assessment.md` | Repository inspection, baseline behavior, files inspected, commands, code locations, constraints, risks |
| `research.md` | Research questions, external-research evaluation, source-derived notes, applicability |
| `links.md` | External source ledger with stable source IDs |
| `findings.md` | Conclusions, options, recommendation, rejected alternatives, assumptions, open questions |
| `plan.md` | Approved implementation approach, ordered steps, validation, risks, rollback or migration considerations |
| `implementation-log.md` | Append-only consequential implementation record and minor deviations |
| `verification.md` | Tests, CI checks, metrics, screenshots, failures, skipped checks, acceptance evidence |
| `review.md` | Same-agent review of the complete diff against scope, plan, criteria, and repository rules |
| `completion.md` | Final outcome, PR and merge metadata, commits, durable summary, remaining risks, archive record |

Reference other artifacts instead of copying large sections between them.

## 5. Authoritative state machine

Normal states, in order:

```text
draft
assessing
researching
awaiting_findings_approval
planning
awaiting_plan_approval
approved
creating_branch
implementing
testing
reviewing
committing
pushing
awaiting_pr_approval
creating_pr
waiting_for_ci
awaiting_merge_approval
merging
completing
completed
archived
```

Exceptional states: `blocked`, `failed`, `cancelled`, and `superseded`.

For every transition, update `status` and `updated_at` in `task.yaml`, append a `state_history` entry, update `.tasks/index.yaml` when practical, and do not jump over a normal state. Enter stages and document `Not applicable` when necessary.

## 6. Intake and task creation

A task may originate from a human request, an agent proposal, a GitHub issue, an audit, or another documented source.

Before assessment, create the task directory from `.tasks/templates/task/`, replace every template value, record the source, populate `task.md`, use stable IDs such as `AC-01` and `PLAN-01`, record the initial repository status, and transition from `draft` to `assessing`.

The original request and approved scope become locked after plan approval. Material scope changes require a revision and renewed approval.

## 7. Pre-branch work

Assessment, research, findings, and planning occur before branch creation. During pre-branch work, only modify files inside the current task directory. Do not modify production source, tests, configuration, generated artifacts, dependencies, or documentation outside it. Record the initial `git status --porcelain`. Before branch creation, verify that every new change belongs to the task directory.

After plan approval, create the task branch while carrying the uncommitted task artifacts onto it.

## 8. Assessment

Inspect the repository before proposing a solution. Record files inspected, consequential commands, architecture, data flow, current and expected behavior, reproduction steps, important paths and symbols, tests, constraints, assumptions, unknowns, and risks. Do not use external research to replace repository inspection.

## 9. External research

The research stage is mandatory, but it may conclude that no external sources are necessary. State the questions considered, explain why repository evidence is sufficient, and mark `links.md` as `Not applicable` with a rationale.

When sources are useful, prefer repository source and current docs, official documentation, primary specifications and research, maintainer repositories and release notes, high-quality secondary sources, then forums only as supporting evidence. Give each source a stable `SRC-###` ID and distinguish sourced claims from inference.

## 10. Findings and approval

`findings.md` synthesizes assessment and research into findings, options, a recommendation, rejected alternatives, assumptions, risks, and open questions. Increment `revisions.findings` for material changes.

Transition to `awaiting_findings_approval` and ask the user to approve the exact findings revision in chat. Record status, revision, approver, timestamp, source, and concise evidence in `task.yaml`. Do not start planning before approval.

## 11. Planning and approval

After findings approval, transition to `planning` and create `plan.md`. Every plan step includes a stable ID, supported criteria, expected files or symbols, method, validation, risks and mitigation, and migration or rollback considerations when applicable. Include prerequisites, dependency or schema changes, test strategy, documentation updates, commit grouping, and exclusions.

Increment `revisions.plan` for material changes. Transition to `awaiting_plan_approval`, ask the user to approve the exact revision in chat, and record it. Do not modify production files before approval.

## 12. Material changes

A material change includes new user-visible behavior outside the plan; weakening acceptance criteria; unexpected public API, data format, architecture, deployment, migration, or security changes; unrelated subsystem expansion; unplanned dependencies; substantially increased risk or effort; or changing the independently mergeable outcome.

Stop, record the proposal, increment the affected revision, invalidate the affected approval, return to the appropriate approval state, and resume only after renewed approval. Minor implementation details and equivalent substitutions go in `implementation-log.md` without renewed approval.

## 13. Working-tree safety and branch creation

After plan approval, transition through `approved` to `creating_branch`. Run the configured status command. Verify task-system changes belong to the task. If unrelated uncommitted work exists, stop and ask. Never stash, discard, reset, clean, overwrite, commit, or absorb unrelated work. Confirm the base branch and remote, create the configured branch, and record branch metadata in `task.yaml`.

## 14. Implementation

Transition to `implementing`. Follow the approved plan and root `AGENTS.md`. Keep `implementation-log.md` append-only while active. Record consequential commands, important changes, discoveries, minor deviations, failures and resolutions, decisions and rejected alternatives, and relevant measurements. Do not log every view or tool call.

Store relevant screenshots under `evidence/screenshots/`. Commit only evidence needed to understand or verify the task.

## 15. Testing and verification

Transition to `testing`. Run relevant formatting, linting, type-checking, unit, integration, end-to-end, build, migration, and security checks according to repository rules.

`verification.md` maps every acceptance criterion to status, commands or procedure, expected and actual results, tests or code locations, metrics, screenshots, commit SHA, and limitations. Record known failures and skipped checks. A task cannot reach merge approval with failed, unverified, or omitted criteria.

## 16. Same-agent review

Transition to `reviewing`. Review the complete diff against the approved task and plan, every acceptance criterion, unrelated changes, conventions, tests, error handling, security, compatibility, dependencies, generated files, documentation, task-artifact accuracy, remaining risks, and skipped checks. Record findings in `review.md` and fix them before continuing. A separate agent is not required.

## 17. Commits and push

Transition to `committing`. Use multiple logical commits when appropriate. Default subject:

```text
TASK-YYYY-NNN: concise imperative summary
```

Record commit SHAs and subjects. Transition to `pushing`, push the task branch, and record the remote and head SHA.

## 18. Pull-request approval and creation

After push, transition to `awaiting_pr_approval`. Present the task summary, criterion status, local verification, review result, commits, risks, failures, skipped checks, and current head SHA. Ask for approval to create the PR. Approval binds to the current head SHA; invalidate it if the branch changes.

After approval, transition to `creating_pr`, create the PR, generate its body from task artifacts, and record PR metadata.

## 19. GitHub workflow checks

Transition to `waiting_for_ci`. Poll checks using `.tasks/config.yaml`. Do not wait for review comments unless separately requested.

On a failed or cancelled required check, inspect it, determine root cause, correct it, run local checks, update records, commit and push, then continue polling. CI fixes within approved scope do not require new PR approval. On timeout or an external blocker, transition to `blocked`, record the blocker, and ask the user.

## 20. Merge approval and merge

When all required checks pass, transition to `awaiting_merge_approval`. Present the PR, exact head SHA, check results, criterion status, remaining risks, failures or skipped checks, and merge strategy. Ask the user for merge approval. Approval binds to the exact head SHA and green state; any later commit invalidates it.

After approval, transition to `merging` and merge using repository policy; if none is discoverable, use squash. Record the merge commit and timestamp.

## 21. Completion and archival

After the implementation PR merges, transition to `completing`. Update `completion.md` with the final outcome, PR, branches, commits, checks, merge metadata, criteria, implementation summary, deviations and approvals, tests and metrics, screenshots, risks, failures, skipped checks, and out-of-scope follow-up work.

Condense durable information from `implementation-log.md`; remove temporary command dumps, downloaded sources, duplicate notes, and irrelevant screenshots. Set the task to `completed`, move it to the dated archive path, and update `task.yaml`.

Create a documentation-only archival branch and PR containing only final metadata, condensed records, the active-to-archive move, and derived index updates. The original merge approval authorizes this mechanical archival PR. Wait for checks and merge it without another approval. If it contains production changes, stop and request approval.

## 22. Research-only and audit tasks

These tasks still follow the full lifecycle. Implementation may consist of approved repository artifacts rather than production code. Mark code-specific sections `Not applicable` with reasons. Branch creation, validation, review, commits, push, approvals, checks, merge, completion, and archive remain required.

## 23. Missing GitHub remote or CI

If the repository lacks a GitHub remote, permissions, branch-protection visibility, or CI workflows, stop and ask the user how to proceed. Do not silently reinterpret the lifecycle. Record the authorized alternative in `task.yaml`, `verification.md`, and `completion.md`.

## 24. Configuration and overrides

`.tasks/config.yaml` contains machine-readable repository policy. The root `AGENTS.md` explains project-specific rules. If configuration, root instructions, repository behavior, and these instructions conflict, stop and ask the user.
