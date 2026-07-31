# Task Lifecycle Instructions

These rules govern the task instance selected by the repository's root `AGENTS.md` and configuration. In ordinary installations, the live instance is `.tasks/`. In the task-system source repository, the live instance is `.project-tasks/` while `.tasks/` remains the distributable product.

## Core rules

1. One independently mergeable unit of work equals one task directory.
2. One agent owns the lifecycle from intake through implementation merge and archival preparation.
3. `task.yaml` is authoritative; Markdown files preserve human-readable evidence.
4. Assessment, external-research evaluation, findings, and a plan are mandatory before implementation.
5. User approval in chat is required for findings, plan, PR creation, and implementation merge.
6. Never silently stash, discard, overwrite, commit, or absorb unrelated work.
7. Every implementing task uses its own branch or worktree.
8. Review the committed production candidate, not only uncommitted files.
9. GitHub workflow checks are the required post-PR gate; review comments are handled when the user requests it or repository policy requires it.
10. A task is completed when the implementation PR merges and archived when its finalized directory exists in the configured archive path on the default branch.

## Paths

Read the active, archive, template, and index paths from the live instance's `config.yaml`. Do not assume that live task records are under `.tasks/`.

The branch convention is:

```text
task/TASK-YYYY-NNN-kebab-case-slug
```

## Required artifacts

Every active task contains:

- `task.yaml`
- `task.md`
- `assessment.md`
- `research.md`
- `links.md`
- `findings.md`
- `plan.md`
- `implementation-log.md`
- `verification.md`
- `review.md`
- `completion.md`
- `evidence/screenshots/`

Sections that do not apply remain present and explain why. Archived tasks preserve the files configured by `archive.preserve`; active-only artifacts such as `implementation-log.md` may be condensed or removed according to `archive.condense_or_remove`.

## Lifecycle

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

Exceptional states are `blocked`, `failed`, `cancelled`, and `superseded`.

Allowed correction loops:

```text
reviewing → implementing → testing → committing → reviewing
waiting_for_ci → implementing → testing → committing → reviewing → pushing → waiting_for_ci
awaiting_merge_approval → implementing → testing → committing → reviewing → pushing → waiting_for_ci
```

For every transition, update `status`, `status_reason`, `updated_at`, and append a connected `state_history` entry. Regenerate the live index with the bundled generator. Do not skip normal states.

## Assessment and research

Record files inspected, consequential commands, architecture, current and expected behavior, important code locations, assumptions, risks, existing tests, validation paths, and the assessed default-branch commit.

External research is a mandatory stage, but it may conclude that repository evidence is sufficient. When no external source is needed, explain why in `research.md`, use `Source-derived notes` with a `Not applicable` rationale, and mark `links.md` not applicable. Research establishes evidence and uncertainty; the final implementation direction belongs in `findings.md`.

## Findings and planning

`findings.md` contains evidence-backed conclusions, options, the recommended direction, rejected alternatives, assumptions, risks, and open questions. Approval binds to the current task and findings revisions plus the SHA-256 digest of `findings.md`.

`plan.md` contains stable `PLAN-##` steps, supported `AC-##` criteria, expected files or symbols, method, validation, risks, mitigation, and migration or rollback details. Approval binds to the current task, findings, and plan revisions plus the SHA-256 digest of `plan.md`.

A material change invalidates affected approvals and requires renewed approval.

## Branch safety

Pre-branch work may modify only the current task directory. Before branch creation, confirm that no unrelated changes exist and compare the current default-branch head with the assessed base commit. Relevant drift requires refreshed assessment and approval as needed.

## Implementation, testing, and review

Keep `implementation-log.md` append-only while active. Each consequential entry records commands, changes, discoveries, decisions, rejected alternatives, failures and resolutions, plan deviations, and metrics or evidence.

Map every acceptance criterion to explicit verification evidence. Every `AC-##` must appear in `task.md`, `verification.md`, and `completion.md`; every `PLAN-##` must appear in `plan.md`. A task cannot reach merge approval with failed, unverified, or omitted criteria.

Commit the production candidate, then review the committed range plus staged, unstaged, and untracked changes. Fix findings through a correction loop before push.

## Approval-bound heads

`git.candidate_head_sha` identifies the reviewed production candidate. PR-creation approval binds to that SHA. A later commit may update only the current task record with PR or CI metadata; such a metadata-only commit does not replace the production candidate. Any commit that changes product code, tests, configuration, generated product artifacts, or user-facing documentation creates a new candidate and invalidates the prior head-bound approval.

Merge approval binds to the exact candidate recorded in `pull_request.head_sha` after required checks for that candidate pass. The validator rejects stale approval revisions, stale candidate SHAs, and merge approvals without passed checks.

## Pull request, CI, and merge

After push, present the candidate head and request PR-creation approval. Create the PR, record its metadata, and wait for required GitHub workflow checks. Fix failed checks or requested review changes through a correction loop.

When checks pass, request merge approval bound to the exact green candidate. Any production change invalidates merge approval. Merge approval may be written into the durable completion/archive record after the implementation PR merges, avoiding a self-referential commit SHA.

## Archival

After implementation merge, finalize `completion.md`, condense durable implementation history, remove temporary evidence, move the task to the dated archive path, regenerate the index, and open a documentation-only archival PR. The archived record does not attempt to contain its archival PR's own merge SHA.
