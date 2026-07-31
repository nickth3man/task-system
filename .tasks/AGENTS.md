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

Use the full lifecycle for:

- Feature implementation
- Bug fix
- Refactor
- Performance improvement
- Security remediation
- Project audit
- Research-only task
- Documentation
- Dependency upgrade
- Data or database work
- UI/UX improvement
- Repository setup or scaffolding
- Other independently mergeable repository work

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

Identifiers are sequential per repository and year. To allocate an ID:

1. Scan every `task.yaml` under `.tasks/active/` and `.tasks/archive/`.
2. Find the highest sequence for the current year.
3. Add one and format it with three digits.
4. Do not rely only on `.tasks/index.yaml` because it is generated and non-authoritative.
5. Stop and resolve any duplicate ID before continuing.

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

Exceptional states:

```text
blocked
failed
cancelled
superseded
```

For every transition:

1. Update `status` and `updated_at` in `task.yaml`.
2. Append an entry to `state_history` with timestamp, previous state, next state, actor, and reason.
3. Update `.tasks/index.yaml` as a derived view when practical.
4. Do not jump over a normal state. Enter it and document `Not applicable` when necessary.

A blocked task records the blocker, the attempted resolution, the date, and the user decision required. Resume from the last valid normal state after the blocker is cleared.

## 6. Intake and task creation

A task may originate from a human request, an agent proposal, a GitHub issue, an audit, or another documented source.

Before assessment:

1. Create the task directory from `.tasks/templates/task/`.
2. Replace every template value in `task.yaml`.
3. Record the source and any issue URL or reference.
4. Populate `task.md` with the exact request, interpreted objective, scope, constraints, non-goals, and stable acceptance-criterion IDs.
5. Use stable IDs such as `AC-01`, `AC-02`, and `PLAN-01`.
6. Record the initial repository status command and result.
7. Transition from `draft` to `assessing`.

The original request and approved scope become locked after plan approval. Correct typos and clarify wording without changing meaning. Material scope changes require a revision and renewed approval.

## 7. Pre-branch work

Assessment, research, findings, and planning occur before branch creation.

During pre-branch work:

- Only modify files inside the current `.tasks/active/<task>/` directory.
- Do not modify production source, tests, configuration, generated artifacts, dependencies, or documentation outside the task directory.
- Record the initial `git status --porcelain` output in `assessment.md` or `implementation-log.md`.
- If unrelated user changes already exist, record them but do not touch them.
- Before branch creation, verify that every new change belongs to the task directory.

After plan approval, create the task branch while carrying the uncommitted task artifacts onto it.

## 8. Assessment

Transition to `assessing` and inspect the repository before proposing a solution.

Record:

- Files inspected
- Consequential repository commands
- Relevant architecture and data flow
- Current and expected behavior
- Reproduction steps for bugs, when applicable
- Important file paths, symbols, and useful line ranges
- Existing tests and validation paths
- Constraints and compatibility requirements
- Assumptions
- Known unknowns
- Initial risks

Do not use external research to replace repository inspection.

## 9. External research

Transition to `researching` after assessment.

The research stage is mandatory, but it may conclude that no external sources are necessary. In that case:

- State the questions considered.
- Explain why repository evidence and established project behavior are sufficient.
- Mark `links.md` as `Not applicable` with the rationale.

When external sources are useful, prefer this hierarchy:

1. Repository source code and current repository documentation
2. Official language, library, framework, API, and platform documentation
3. Primary specifications, standards, or research
4. Maintainer repositories, issues, release notes, and migration guides
5. High-quality secondary technical sources
6. Forums and informal discussion only as supporting evidence

For each external source, add a stable ID in `links.md`, such as `SRC-001`, and record authority, access date, relevance, and where it influenced the task. In `research.md`, distinguish source-derived claims from inference.

## 10. Findings and findings approval

`findings.md` synthesizes assessment and research into:

- Evidence-backed findings
- Viable options
- Recommended direction
- Rejected alternatives and reasons
- Assumptions
- Risks
- Open questions

Increment `revisions.findings` whenever the findings change materially.

Transition to `awaiting_findings_approval` and ask the user to approve the current findings revision in chat. Record:

- `status: approved`
- Approved revision
- Approver
- Timestamp
- `source: chat`
- Concise evidence of what was approved

Do not start planning before findings approval.

## 11. Planning and plan approval

After findings approval, transition to `planning` and create `plan.md`.

Every plan step must include:

- Stable plan ID
- Supported acceptance criteria
- Expected files or symbols
- Method
- Validation command or procedure
- Risks and mitigation
- Migration or rollback considerations when applicable

Also include:

- Prerequisites
- Expected dependency or schema changes
- Test strategy
- Documentation updates
- Commit grouping
- Explicit exclusions

Increment `revisions.plan` for material plan changes.

Transition to `awaiting_plan_approval` and ask the user to approve the exact plan revision in chat. Record the approval in `task.yaml`. Do not modify production files before plan approval.

## 12. Material changes and approval invalidation

A material change includes any of the following:

- Adding user-visible behavior outside the approved plan
- Removing or weakening an acceptance criterion
- Unexpectedly changing a public API, persistent data format, architecture, deployment, migration, or security behavior
- Expanding into unrelated files or subsystems
- Adding a dependency not anticipated by the approved plan
- Substantially increasing risk or effort
- Changing the task's independently mergeable outcome

For a material change:

1. Stop implementation.
2. Record the reason and proposed change.
3. Increment the affected artifact revision.
4. Mark the affected approval `invalidated`.
5. Return to the appropriate approval state.
6. Resume only after renewed approval in chat.

Minor implementation details and equivalent technical substitutions are recorded in `implementation-log.md` without renewed approval.

## 13. Working-tree safety and branch creation

After plan approval, transition to `approved`, then `creating_branch`.

Before creating the branch:

1. Run the configured status command, normally `git status --porcelain`.
2. Verify all uncommitted task-system changes belong to the current task directory.
3. If unrelated uncommitted work exists, stop and ask the user.
4. Do not stash, discard, reset, clean, overwrite, commit, or absorb unrelated work.
5. Confirm the base branch and remote.
6. Create the configured branch name.
7. Record the base branch, branch name, creation timestamp, and base commit in `task.yaml`.

## 14. Implementation

Transition to `implementing`.

Follow the approved plan and root `AGENTS.md`. Keep `implementation-log.md` append-only during active implementation.

Record only consequential information:

- Commands that establish state, generate files, reproduce problems, or affect decisions
- Important code changes
- Discoveries that alter implementation details
- Minor plan deviations
- Failures and resolutions
- Decisions and rejected alternatives
- Relevant before/after measurements

Do not log every file view, navigation command, tool call, or conversational exchange.

Store relevant screenshots under:

```text
evidence/screenshots/
```

Commit only screenshots needed to understand or verify the task. Remove temporary screenshots before archival.

## 15. Testing and verification

Transition to `testing`.

Run the repository's relevant formatting, linting, type-checking, unit, integration, end-to-end, build, migration, and security checks. Follow the root `AGENTS.md` and `.tasks/config.yaml`.

`verification.md` must map every acceptance criterion to explicit evidence:

- Status
- Commands or procedure
- Expected result
- Actual result
- Test names or code locations
- Metrics
- Screenshot paths when relevant
- Commit SHA when available
- Limitations

Record:

- Test commands and results
- Before/after metrics
- GitHub workflow results once the PR exists
- Known failures
- Skipped tests and reasons
- Environment limitations

A task cannot reach merge approval with an acceptance criterion failed, unverified, or silently omitted. Any accepted limitation requires explicit user authorization and a recorded scope or criterion update.

## 16. Same-agent review

Transition to `reviewing` after local verification.

The implementing agent reviews the complete diff against the base branch. Review:

- Approved task and plan
- Every acceptance criterion
- Unrelated or accidental changes
- Repository conventions
- Tests and coverage
- Error handling
- Security and privacy
- Compatibility and migrations
- Dependencies and generated files
- Documentation
- Task-artifact accuracy
- Remaining risks and skipped checks

Record findings in `review.md`. Fix review findings before continuing. A separate agent or fresh-context review is not required.

## 17. Commits and push

Transition to `committing`.

Use multiple logical commits when appropriate. Default commit subject:

```text
TASK-YYYY-NNN: concise imperative summary
```

Do not create temporary failing-work commits merely as checkpoints unless repository policy requires them. Ensure each committed change belongs to the approved task.

Record commit SHAs and subjects in `task.yaml` and `completion.md`.

Transition to `pushing`, push the task branch, and record the remote and head SHA.

## 18. Pull-request approval and creation

After push, transition to `awaiting_pr_approval`.

Present the user with:

- Task ID and title
- Final scope summary
- Acceptance-criterion status
- Local verification summary
- Review result
- Commit list
- Remaining risks, failures, and skipped checks
- Current branch head SHA

Ask for approval to create the pull request. Approval binds to the current head SHA. If the branch changes before PR creation, invalidate the approval and ask again.

After approval, transition to `creating_pr` and create the PR.

Generate the PR body from task artifacts with:

- Task ID and summary
- Acceptance-criterion checklist
- Validation commands
- Risks and limitations
- Path to the active task record

Record PR number, URL, base branch, head branch, and head SHA in `task.yaml`.

## 19. GitHub workflow checks

Transition to `waiting_for_ci`.

Poll GitHub workflow checks using `.tasks/config.yaml`:

- Poll interval: configured value
- Timeout: configured value
- Required checks: repository policy or discovered branch-protection requirements

Do not wait for human or automated review comments unless the user separately requests it.

On a failed or cancelled required check:

1. Inspect the failure.
2. Determine root cause.
3. Implement the correction.
4. Run relevant local checks.
5. Update verification and implementation records.
6. Commit and push.
7. Continue polling.

CI fixes within the approved scope do not require a new PR-creation approval. Material scope changes still require the normal approval process.

On timeout or an external blocker, transition to `blocked`, record the blocker, and ask the user how to proceed.

## 20. Merge approval and merge

When every required GitHub workflow check passes, transition to `awaiting_merge_approval`.

Present:

- PR URL and number
- Exact current head SHA
- Required check results
- Acceptance-criterion status
- Remaining risks
- Known failures or skipped checks
- Intended merge strategy

Ask the user for merge approval in chat. Approval binds to the exact head SHA and green-check state. Any subsequent commit invalidates merge approval and requires checks plus renewed approval.

After approval, transition to `merging` and merge using repository policy. If no policy is discoverable, use squash merge. Record the merge commit and timestamp.

## 21. Completion and archival

After the implementation PR merges, transition to `completing`.

Update `completion.md` with:

- Final outcome
- PR URL and number
- Branch and base branch
- Commit list
- Workflow-check results
- Merge strategy, commit, and timestamp
- Acceptance-criterion summary
- Implementation summary
- Material deviations and approvals
- Tests and before/after metrics
- Relevant screenshot paths
- Remaining risks
- Known failures and skipped checks
- Follow-up work explicitly outside scope

Condense durable information from `implementation-log.md` into `completion.md`. Remove temporary command dumps, downloaded sources, duplicate notes, and irrelevant screenshots.

Set the task to `completed`, move it to the configured dated archive path, and update the path in `task.yaml`.

Create a documentation-only archival branch and PR containing only:

- Final metadata updates
- Condensed task records
- The move from active to archive
- Derived index updates

The original merge approval authorizes this mechanical archival PR. Wait for required checks and merge it without another user approval. If the archival diff contains production changes or non-mechanical scope, stop and request explicit approval.

After the archival PR merges, set the final state to `archived` and record the archival PR and merge metadata. If branch protection prevents the final state from being recorded without another PR, record `archived` in the archival PR before merge and include the expected archival merge metadata where exact values are not yet available; update through the repository's normal documentation process only when required.

## 22. Research-only and audit tasks

Research-only and audit tasks still follow the full lifecycle. Their implementation may consist of adding or updating approved repository artifacts rather than production code. Mark code-specific sections `Not applicable` with reasons. They still require branch creation, validation, review, commits, push, PR approval, GitHub checks, merge approval, merge, completion, and archive.

## 23. Missing GitHub remote or CI

The normal standard requires GitHub, workflow checks, and a PR. If the repository lacks a GitHub remote, permissions, branch protection visibility, or CI workflows, stop and ask the user how to proceed. Do not silently reinterpret the lifecycle. Record the user-authorized alternative in `task.yaml`, `verification.md`, and `completion.md`.

## 24. Configuration and overrides

`.tasks/config.yaml` contains machine-readable repository policy. The root `AGENTS.md` explains project-specific rules. Valid overrides must be explicit in configuration and documented in prose.

If configuration, root instructions, repository behavior, and these lifecycle instructions conflict, stop and ask the user. Do not silently choose the most convenient rule.
