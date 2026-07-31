# Cross-Project Task System

A repository-local workflow for taking one independently mergeable unit of work from intake through assessment, research, findings, approval, planning, implementation, verification, review, GitHub CI, merge, and durable archival.

Version 2 adds executable validation, deterministic index generation, artifact-digest approvals, explicit correction loops, committed-head review, safe pre-branch handling, base-drift checks, and one-pass archival.

## Core rule

One independently mergeable unit of work equals one task directory.

Keep changes together when they share one acceptance outcome and must ship atomically. Split them when they solve different problems, can be reviewed or merged separately, have different risks or approvals, or one can be abandoned without invalidating the other.

## Repository layout

```text
AGENTS.md                         # live project-specific instructions
AGENTS.project-template.md        # template for adopting projects
requirements-dev.txt              # validator dependencies
scripts/
├── validate.py                   # schema + semantic validation
└── generate_index.py             # deterministic index generation
.github/workflows/validate.yml    # validation workflow
.tasks/
├── AGENTS.md                     # lifecycle rules
├── VERSION
├── config.yaml                   # live repository configuration
├── index.yaml                    # generated navigation view
├── schemas/
│   ├── config.schema.json
│   └── task.schema.json
├── templates/
│   ├── config.yaml               # consumer configuration template
│   └── task/
├── active/
└── archive/YYYY/MM/
```

`task.yaml` is authoritative for task state. Markdown artifacts contain the request, evidence, findings, plan, implementation history, verification, review, and completion record. `.tasks/index.yaml` is derived and must never allocate IDs or override a task record.

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

Correction loops are explicit:

```text
reviewing → implementing → testing → committing → reviewing
waiting_for_ci → implementing → testing → committing → reviewing → pushing → waiting_for_ci
```

Exceptional states are `blocked`, `failed`, `cancelled`, and `superseded`.

`completed` means the implementation pull request merged. `archived` means the finalized task directory exists under `.tasks/archive/` on the default branch.

## Approval gates

The user approves in chat at four points:

1. Findings approval, bound to the findings revision and SHA-256 digest.
2. Plan approval, bound to the plan revision/digest and the task/findings revisions it depends on.
3. Pull-request creation approval, bound to the exact pushed head SHA.
4. Merge approval, bound to the exact PR head SHA while required checks are green.

A material task, findings, or plan change invalidates affected approvals. Any new commit invalidates merge approval.

## Review model

Review occurs after the candidate change has been committed. The agent reviews the committed range from the assessed/base commit to the current head, plus staged, unstaged, and untracked-file safety checks.

This prevents `base...HEAD` commands from silently omitting uncommitted implementation work. Review findings loop back through implementation, testing, committing, and review before push.

## Pre-branch safety

Assessment, research, findings, and planning are written before branch creation. Their uncommitted files are allowed, but they must be the only uncommitted changes in that worktree.

The system requires no unrelated changes, not a completely clean worktree. The agent never automatically stashes or discards user work.

Immediately before branch creation, the agent checks whether the default branch changed since assessment. Relevant drift refreshes assessment and invalidates approvals when necessary.

## CI and merge behavior

`required_checks_mode` distinguishes three cases:

- `discover`: inspect repository requirements and check runs.
- `explicit`: require configured check names.
- `none`: intentionally use no checks through an explicit repository policy.

An empty `required_checks` list is not automatically success. Under discovery mode, finding no checks follows `on_no_checks_discovered`, which defaults to `stop_and_ask`.

The merge method follows repository policy. When repository settings allow several methods without selecting one, the configured ambiguity rule applies; the default fallback is squash.

## One-pass archival

After the implementation PR merges, a documentation-only archival PR:

1. Finalizes implementation merge metadata.
2. Condenses durable implementation history.
3. Removes temporary evidence.
4. Moves the task from active to its dated archive path.
5. Records archival PR metadata and inherited authorization.
6. Regenerates the task index.

The archived record does not try to contain the archival PR's own merge SHA or merge timestamp. That information cannot be truthfully written inside the same PR before it merges. Presence of the task directory in the archive on the default branch is the proof of archival.

## Validation

Install the validation dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run all checks:

```bash
python scripts/validate.py
```

The validator checks:

- Configuration and task JSON Schemas
- Semantic state and approval invariants
- Approval revision, digest, and head-SHA bindings
- Allowed lifecycle transitions and correction loops
- Unique task, acceptance-criterion, and plan-step IDs
- Plan-step references to real acceptance criteria
- Required active artifacts
- Active/archive status and path consistency
- Blocker resume metadata
- Unreplaced live placeholders
- Unresolved merge-conflict markers
- Task-system version consistency
- Generated index consistency

Regenerate the index:

```bash
python scripts/generate_index.py
```

Check without writing:

```bash
python scripts/generate_index.py --check
```

GitHub Actions runs the same validator on pushes and pull requests.

## Install into another repository

1. Copy `.tasks/`, `scripts/validate.py`, `scripts/generate_index.py`, and `requirements-dev.txt` into the target repository.
2. Copy `AGENTS.project-template.md` to the target repository as `AGENTS.md`, or merge its task-system section into an existing root `AGENTS.md`.
3. Replace `.tasks/config.yaml` with `.tasks/templates/config.yaml`, then fill every `__REQUIRED_*__` value and repository-specific command.
4. Merge `.github/workflows/validate.yml` into the target repository's workflows. Rename the workflow or job only if the configured required-check policy is updated with it.
5. Run `python scripts/generate_index.py` and `python scripts/validate.py`.
6. Commit the installation through the target repository's normal review process.

The live `.tasks/config.yaml` in this repository is configured for `nickth3man/task-system`; it is not the consumer template.

## Start a task

Allocate the next repository/year sequence by scanning active tasks, archived tasks, and remote task branches. Recheck after creating the directory to detect concurrent allocation.

Copy the task template:

```bash
cp -R .tasks/templates/task .tasks/active/TASK-2026-001-example-task
```

PowerShell:

```powershell
Copy-Item .tasks\templates\task .tasks\active\TASK-2026-001-example-task -Recurse
```

Replace every `__REQUIRED_*__` value. The template is intentionally schema-invalid until initialized, preventing placeholder task records from passing validation accidentally.

## Versioning

The system uses semantic versioning:

- Patch: compatible wording, examples, or template corrections.
- Minor: new optional fields or artifacts.
- Major: required schema, lifecycle, state, approval, or archival changes.

Each task records the task-system version under which it was created. Archived records do not need to be rewritten for a later major version unless a migration is explicitly required.

## License

This project is available under the MIT License.
