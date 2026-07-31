# Cross-Project Task System

A repository-local workflow for taking one feature, bug fix, refactor, audit, research task, documentation change, dependency update, data change, UI/UX improvement, security remediation, performance improvement, or scaffolding task from intake through a merged pull request and durable archive.

The system is intentionally instruction- and template-based in version 1. It does not require a CLI. Each repository receives its own editable copy of `.tasks/`, while a central template repository remains the distribution source.

## Core rule

One independently mergeable change equals one task directory.

A task may touch many files and contain many implementation steps, but it should produce one coherent pull request. Split work into separate task directories when changes solve different problems, can be reviewed or merged independently, have different risks or approvals, or one can be abandoned without invalidating the other.

## Repository layout

```text
AGENTS.md                         # project-specific development instructions
.tasks/
├── AGENTS.md                    # task lifecycle and evidence rules
├── VERSION
├── config.yaml
├── index.yaml                   # generated view; never authoritative
├── schemas/
│   ├── config.schema.json
│   └── task.schema.json
├── templates/
│   └── task/
│       ├── task.yaml
│       ├── task.md
│       ├── assessment.md
│       ├── research.md
│       ├── links.md
│       ├── findings.md
│       ├── plan.md
│       ├── implementation-log.md
│       ├── verification.md
│       ├── review.md
│       ├── completion.md
│       └── evidence/
│           └── screenshots/
├── active/
└── archive/
    └── YYYY/
        └── MM/
```

`task.yaml` is the authoritative state record for a task. Markdown artifacts explain the work and preserve evidence. `.tasks/index.yaml` is a generated convenience view and must never override a task's own `task.yaml`.

## Mandatory lifecycle

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
→ reviewing
→ committing
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

Every stage is entered. When a stage or section does not apply, it is marked `Not applicable` with a reason rather than silently omitted.

## Approval gates

The user approves in chat at four points:

1. Findings approval: assessment, external-research evaluation, and findings are accepted.
2. Plan approval: the implementation plan and scope are accepted.
3. Pull-request approval: the reviewed branch is approved for PR creation.
4. Merge approval: all required GitHub workflow checks are green and the exact PR head is approved for merge.

The agent records each approval in `task.yaml`. Findings and plan approvals bind to artifact revisions. Pull-request and merge approvals bind to the branch head SHA. A material scope change invalidates the affected approval.

## Git and GitHub behavior

- Branch names use `task/TASK-YYYY-NNN-kebab-case-slug`.
- The agent checks the working tree before branch creation.
- If unrelated uncommitted work exists, the agent stops and asks the user. It never silently stashes, discards, overwrites, commits, or absorbs user work.
- Commits are incremental and logically grouped.
- The agent pushes the task branch, requests approval to create the PR, creates the PR after approval, and waits for GitHub workflow checks.
- It does not wait for review comments unless the user separately requests that behavior.
- Failed checks are fixed locally, committed, pushed, and rechecked until green or until the configured timeout or an external blocker is reached.
- The agent asks for merge approval only after all required checks pass.
- The merge strategy follows repository policy; if none is discoverable, squash merge is the fallback.

## Post-merge archival

After the implementation PR merges, the agent:

1. Records the PR, merge commit, checks, commits, remaining risks, known failures, skipped checks, and relevant metrics in `completion.md`.
2. Condenses durable information from `implementation-log.md` into `completion.md`.
3. Removes temporary command dumps, downloaded research material, duplicate notes, and irrelevant screenshots.
4. Moves the task to `.tasks/archive/YYYY/MM/<task-directory>/`.
5. Opens a documentation-only archival PR.
6. Waits for CI and merges the archival PR without another user approval, because the user's implementation merge approval authorizes this mechanical archival step.

If the archival diff contains production changes, the agent stops and requests explicit approval.

## Install into a repository

1. Copy `.tasks/` into the target repository.
2. Copy `AGENTS.example.md` to `AGENTS.md`, or merge its task-system section into the repository's existing `AGENTS.md`.
3. Edit `.tasks/config.yaml` for repository-specific commands, default branch, timezone, GitHub settings, and overrides.
4. Commit the initial task-system files through the repository's normal review process.

## Start a task manually

Allocate the next repository-scoped yearly ID by scanning all existing `task.yaml` files in `.tasks/active/` and `.tasks/archive/`. Never rely only on `index.yaml`.

Example:

```text
TASK-2026-007
```

Copy the template directory:

```bash
cp -R .tasks/templates/task .tasks/active/TASK-2026-007-add-query-timeouts
```

PowerShell:

```powershell
Copy-Item .tasks\templates\task .tasks\active\TASK-2026-007-add-query-timeouts -Recurse
```

Then replace the template values in `task.yaml`, populate `task.md`, append the initial state transition, and begin the lifecycle defined in `.tasks/AGENTS.md`.

## Update the generated index

`index.yaml` is a derived navigation aid. Regenerate it by scanning task directories and copying only identifiers, titles, statuses, and paths from each authoritative `task.yaml`. Do not store unique decisions or approval data only in the index.

## Versioning

The task system uses semantic versioning:

- Patch: compatible wording, examples, or template corrections.
- Minor: new optional fields or artifacts.
- Major: required schema or lifecycle changes.

Each task records the task-system version under which it was created. Existing archived tasks do not need to be rewritten when the template changes.

## Future automation

After this workflow has been exercised across several repositories, a CLI may automate initialization, ID allocation, schema validation, index generation, state transitions, approvals, and archival. Until then, agents edit the files directly and follow `.tasks/AGENTS.md` exactly.
