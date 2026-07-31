# Task Lifecycle Instructions for Agents

These instructions govern work recorded under `.tasks/`. Repository development rules remain in the root `AGENTS.md`; both files apply.

## 1. Non-negotiable principles

1. One independently mergeable unit of work equals one task directory.
2. One agent owns the task from intake through implementation merge and archival preparation.
3. `task.yaml` is the authoritative machine-readable record.
4. Markdown artifacts preserve the request, evidence, decisions, implementation history, verification, review, and outcome.
5. Every normal stage is entered. Use `Not applicable` with a concrete reason rather than silently omitting required analysis.
6. Production files are not changed before findings approval, plan approval, and branch creation.
7. The agent never silently stashes, discards, resets, cleans, overwrites, commits, or incorporates unrelated user work.
8. User approval in chat is required for findings, plan, pull-request creation, and implementation merge.
9. `completed` means the implementation pull request merged. `archived` means the task record exists under the configured archive path on the default branch.
10. GitHub workflow checks—not review comments—are the required post-PR gate unless the user explicitly requests review-comment handling.

## 2. Supported task types

Use the full lifecycle for features, bug fixes, refactors, performance work, security remediation, audits, research-only work, documentation, dependency changes, data/database changes, UI/UX changes, scaffolding, and other independently mergeable repository work.

All task types use the same artifact set. Sections that do not apply remain present and state why.

## 3. Directories, identifiers, and concurrency

Active task path:

```text
.tasks/active/TASK-YYYY-NNN-kebab-case-slug/
```

Archive path:

```text
.tasks/archive/YYYY/MM/TASK-YYYY-NNN-kebab-case-slug/
```

Branch:

```text
task/TASK-YYYY-NNN-kebab-case-slug
```

To allocate an ID:

1. Fetch the latest default branch.
2. Scan every `task.yaml` under `.tasks/active/` and `.tasks/archive/`.
3. Scan remote task branches matching the configured branch pattern.
4. Select the next sequence for the current year.
5. Create the task directory and immediately recheck for collisions.
6. On collision, discard only the uncommitted allocation attempt and retry with the next sequence.
7. Never rely on `.tasks/index.yaml` for allocation.

Multiple active tasks may coexist. A worktree may contain only one pre-branch task. Every implementing task uses its own branch or worktree. Never carry another task's artifacts onto a task branch.

## 4. Required artifacts

| Artifact | Primary responsibility |
|---|---|
| `task.yaml` | State, approvals, revisions, acceptance references, Git/PR/merge/archive metadata |
| `task.md` | Original request, objective, scope, constraints, non-goals, acceptance-criterion text |
| `assessment.md` | Repository inspection, baseline, commands, code locations, assumptions, risks |
| `research.md` | Research questions, source-derived notes, applicability, uncertainty |
| `links.md` | External source ledger with stable source IDs |
| `findings.md` | Conclusions, options, recommendation, rejected alternatives, open questions |
| `plan.md` | Approved implementation approach, ordered steps, validation, risks, rollback/migration |
| `implementation-log.md` | Append-only consequential implementation and correction history |
| `verification.md` | Acceptance evidence, tests, metrics, screenshots, failures, skipped checks, CI |
| `review.md` | Review of the committed head against scope, plan, criteria, and repository rules |
| `completion.md` | Implementation PR outcome, commits, merge, durable history, risks, archive preparation |

Reference other artifacts rather than copying large sections wholesale.

## 5. Normal lifecycle and allowed correction loops

Normal progression:

```text
draft
→ assessing
→ researching
→ awaiting_findings_approval
→ planning
→ awaiting_plan_approval
→ approved
→ creating_branch
→ implementing
→ testing
→ committing
→ reviewing
→ pushing
→ awaiting_pr_approval
→ creating_pr
→ waiting_for_ci
→ awaiting_merge_approval
→ merging
→ completing
→ completed
→ archived
```

Exceptional states:

```text
blocked
failed
cancelled
superseded
```

Allowed correction loops:

```text
reviewing → implementing → testing → committing → reviewing
waiting_for_ci → implementing → testing → committing → reviewing → pushing → waiting_for_ci
```

A correction within approved scope does not require renewed findings, plan, or PR-creation approval. Any changed head invalidates merge approval. A material scope change follows the approval-invalidation process.

For every transition:

1. Update `status`, `status_reason`, and `updated_at`.
2. Append `state_history` with timestamp, from, to, actor, and reason.
3. Maintain the task metadata required for the destination state.
4. Regenerate `.tasks/index.yaml` only with the configured generator.
5. Never invent a transition that is not normal, exceptional, or an allowed correction loop.

## 6. Intake

A task may originate from a human request, agent proposal, GitHub issue, audit, or another documented source.

Before assessment:

1. Copy `.tasks/templates/task/` into the active task path.
2. Replace every `__REQUIRED_*__` value.
3. Record the source and exact request.
4. Define one independently mergeable objective.
5. Create observable acceptance criteria with stable IDs such as `AC-01`.
6. Record the current default branch and initial repository status.
7. Transition from `draft` to `assessing`.

The task contract becomes locked after plan approval. Material contract changes increment `revisions.task` and invalidate affected approvals.

## 7. Pre-branch work and worktree safety

Assessment, research, findings, and planning occur before branch creation. During this phase:

- Modify only the current `.tasks/active/<task>/` directory.
- Task artifacts may be uncommitted; this is permitted.
- Do not modify production source, tests, project configuration, dependencies, generated artifacts, or documentation outside the task directory.
- Record the initial `git status --porcelain` result.
- If unrelated changes exist, stop and ask the user before branch creation.
- A clean worktree is not required; absence of unrelated changes is required.

After plan approval, verify that every uncommitted change belongs to the current task directory, then create the task branch while carrying those task artifacts onto it.

## 8. Assessment and base-drift control

Inspect the repository before proposing a solution. Record files inspected, consequential commands, relevant architecture and data flow, current and expected behavior, reproduction steps, important paths/symbols/line ranges, existing tests, constraints, assumptions, unknowns, and risks.

Record the assessed default-branch commit and assessment timestamp in `task.yaml`.

Immediately before branch creation:

1. Fetch the current default branch.
2. Compare it with `assessment.base_commit`.
3. Inspect intervening changes relevant to the task.
4. If relevant behavior, files, APIs, dependencies, or assumptions changed, refresh assessment and invalidate findings or plan approval as necessary.
5. If changes are irrelevant, record that conclusion and continue.

External research never replaces repository inspection.

## 9. External research

The research stage is mandatory. It may conclude that no external sources are necessary, but `research.md` must state the questions considered and why repository evidence is sufficient; `links.md` then states `Not applicable` with the same rationale.

When sources are useful, prefer:

1. Repository source and current repository documentation
2. Official language, library, framework, API, and platform documentation
3. Primary specifications, standards, or research
4. Maintainer repositories, issues, release notes, and migration guides
5. High-quality secondary sources
6. Forums only as supporting evidence

Assign each source a stable `SRC-###` ID. Record authority, access date, relevance, and use. Separate sourced facts from inference.

## 10. Findings approval

`findings.md` contains evidence-backed findings, viable options, recommendation, rejected alternatives, assumptions, risks, and open questions.

For a material findings change:

1. Increment `revisions.findings`.
2. Compute the SHA-256 digest of the exact `findings.md` bytes.
3. Transition to `awaiting_findings_approval`.
4. Ask the user to approve that revision and digest in chat.
5. Record revision, digest, task revision, approver, timestamp, source, and concise evidence.

Do not start planning before the exact findings artifact is approved. Any later content change invalidates the approval unless it is demonstrably non-material; even non-material edits require recomputing and recording the digest before relying on the approval.

## 11. Plan approval

After findings approval, create `plan.md`. Every plan step includes:

- Stable `PLAN-##` ID
- Supported acceptance criteria
- Expected files or symbols
- Method
- Validation
- Risks and mitigation
- Rollback or migration considerations when applicable

Also record prerequisites, dependency/schema/generated-file changes, test strategy, documentation updates, logical commit grouping, and exclusions.

For a material plan change:

1. Increment `revisions.plan`.
2. Compute the SHA-256 digest of `plan.md`.
3. Transition to `awaiting_plan_approval`.
4. Ask the user to approve that revision and digest in chat.
5. Record the approved plan revision/digest plus the task and findings revisions it depends on.

Do not modify production files before plan approval and branch creation.

## 12. Material changes

Material changes include new user-visible behavior outside the plan; weakening acceptance criteria; unexpected public API, persistent data, architecture, deployment, migration, compatibility, or security changes; unrelated subsystem expansion; unplanned dependencies; substantial risk/effort increases; or a different independently mergeable outcome.

On a material change:

1. Stop.
2. Record the discovery and proposed change.
3. Increment affected revisions.
4. Mark affected approvals `invalidated`.
5. Return to the appropriate approval state.
6. Resume only after renewed approval.

Minor implementation substitutions remain in `implementation-log.md` and do not require renewed approval.

## 13. Branch creation

After plan approval:

1. Transition through `approved` to `creating_branch`.
2. Recheck base drift.
3. Run the configured status and untracked-file commands.
4. Verify all uncommitted changes belong to this task.
5. Stop and ask if unrelated changes exist.
6. Create the configured branch.
7. Record branch name, base branch, base commit, creation time, and optional worktree path.

## 14. Implementation and testing

Transition to `implementing` and follow the approved plan plus root `AGENTS.md`.

Keep `implementation-log.md` append-only while active. Record consequential commands, important changes, discoveries, decisions, rejected alternatives, minor deviations, failures/resolutions, and before/after measurements. Do not record every file view or tool call.

Store only relevant screenshots under `evidence/screenshots/`.

Transition to `testing` and run applicable formatting, linting, type-checking, unit, integration, end-to-end, build, migration, security, and repository-specific validation commands.

`verification.md` maps every acceptance criterion to explicit expected/actual results and evidence. A task cannot reach merge approval with a failed, unverified, or omitted acceptance criterion.

## 15. Commit before review

After local verification, transition to `committing`. Create logical commits representing the full candidate change. Record SHAs and subjects.

The committed head—not merely the working tree—is the review target. Before review, require:

- No unintended staged changes
- No unintended unstaged changes
- No unintended untracked files
- A recorded head SHA

## 16. Same-agent review

Transition to `reviewing`. Review the committed diff from the recorded base commit to the current head. The configured `diff_base` and `diff_full` commands must compare committed history.

Review scope, acceptance criteria, plan conformance, unrelated changes, correctness, tests, error handling, security/privacy, performance, compatibility/migrations, dependencies, generated files, documentation, task-artifact accuracy, remaining risks, and skipped checks.

If changes are required, use the review correction loop. Retest, commit, and review the new committed head. Do not push a head whose review verdict is not approved.

## 17. Push and PR approval

After an approved review, transition to `pushing`, push the branch, and record the exact remote head SHA.

Transition to `awaiting_pr_approval` and present the task summary, acceptance status, local validation, review verdict, commits, remaining risks/failures/skips, and head SHA. User approval binds to that SHA and task/plan revisions.

If the head changes before PR creation, invalidate PR approval and ask again.

After approval, create the PR, record its metadata, and generate its body from task artifacts.

## 18. GitHub workflow checks

Transition to `waiting_for_ci`. Determine checks according to `required_checks_mode`:

- `explicit`: require every configured name.
- `discover`: inspect branch protection and workflow/check results. If none are discoverable, follow `on_no_checks_discovered`; never assume an empty list means success.
- `none`: permitted only through an explicit repository configuration and rationale.

Poll at the configured interval until all required checks pass, one fails/cancels, or timeout occurs.

For a failed check, use the CI correction loop: implement, test, commit, review, push, and return to `waiting_for_ci`. Do not request merge approval for an outdated head.

On timeout or external blockage, enter `blocked` and record the prior status, attempted resolutions, required decision, and resume status.

## 19. Merge approval and implementation completion

When all required checks pass, transition to `awaiting_merge_approval`. Present the PR, exact head SHA, checks, acceptance status, remaining risks, known failures/skips, and intended merge method.

Merge approval binds to the exact green head SHA. Any subsequent commit invalidates it.

After approval, transition to `merging`. Follow repository policy. When policy permits multiple methods without selecting one, follow `on_ambiguous_repository_policy`; the default fallback is squash.

After the implementation PR merges:

1. Record the implementation merge commit and timestamp.
2. Set the PR state to `merged`.
3. Transition through `completing` to `completed`.
4. Treat the independently mergeable task as delivered.

## 20. One-pass archival

Prepare one documentation-only archival PR after implementation completion.

Before opening it:

1. Complete `completion.md` with implementation PR and merge metadata.
2. Condense durable information from `implementation-log.md`.
3. Remove temporary command dumps, downloaded sources, duplicate notes, and irrelevant screenshots.
4. Move the directory to the configured archive path.
5. Set task `status: archived` and `archive.status: archived` in the archival branch. These values become effective when that branch lands on the default branch.
6. Record archive authorization as inherited from the implementation merge approval.
7. Regenerate the index.

Open the archival PR, then record its number, URL, branch, and exact head SHA by committing that metadata to the same archival PR. Wait for required checks and merge it without another user approval. Do not attempt to record the archival PR's own merge commit inside the same archived record; the directory's presence on the default branch is the authoritative proof of archival.

If the archival diff contains production changes or non-mechanical scope, stop and request explicit approval.

## 21. Blocked tasks

When entering `blocked`, record:

- `entered_from_status`
- Reason and timestamp
- Attempted resolutions
- Required user decision
- Intended `resume_status`

When resolved, record resolution and time, clear `is_blocked`, and transition to the recorded resume state. Never guess the resume point.

## 22. Validation and generated index

Before commit, before PR creation, after CI corrections, and during archival preparation, run the configured task-system validator.

The validator must check JSON Schema, semantic lifecycle invariants, approval bindings, unique IDs, plan-to-criterion references, required artifacts, unresolved conflict markers, active/archive consistency, placeholder removal in live records, and index consistency.

Generate `.tasks/index.yaml` only with the configured generator. It is a navigation aid, not a source of IDs, approvals, or state.

## 23. Missing GitHub or CI capability

The normal standard requires GitHub, a PR, and workflow checks. If the remote, permission, branch-protection visibility, or CI capability is unavailable, stop and ask the user to authorize an alternative. Record that authorization in `task.yaml`, `verification.md`, and `completion.md`.

## 24. Configuration conflicts

`.tasks/config.yaml` is machine-readable policy. Root `AGENTS.md` describes project-specific development rules. If configuration, schemas, repository behavior, root instructions, and this lifecycle disagree, stop and resolve the conflict rather than silently choosing a convenient interpretation.
