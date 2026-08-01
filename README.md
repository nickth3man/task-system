# Cross-Project Task System

A repository-local, AI-agent-friendly workflow for taking one independently mergeable unit of work from intake through assessment, research, findings, planning, implementation, verification, review, CI, merge, and durable archival.

## Two roles in this source repository

This repository deliberately separates the **task-system product** from the **task records used to develop the product**.

```text
.tasks/          distributable product; copy this directory into another repository
.project-tasks/  live task instance for nickth3man/task-system itself
```

The `.tasks/` directory must remain generic. It contains no real active or archived tasks and no configuration initialized for this repository. All changes to the task-system product are governed by live task records under `.project-tasks/`.

Adopting repositories normally do not need `.project-tasks/`. After a copied `.tasks/` bundle is validated and initialized, that directory changes from a pristine template into the repository's live task instance.

## Copy-and-paste installation

1. Copy the entire `.tasks/` directory into the target repository.
2. Install the bundled dependencies:

   ```bash
   python -m pip install -r .tasks/requirements.txt
   ```

3. Validate the untouched distributable bundle:

   ```bash
   python .tasks/scripts/validate.py --template-only --template-root .tasks
   ```

4. Initialize `.tasks/config.yaml` by replacing every `__REQUIRED_*__` value and changing `mode: template` to `mode: live`.
5. Copy `.tasks/templates/AGENTS.md` to the target repository root as `AGENTS.md`, or merge its task-system section into an existing root file.
6. Copy `.tasks/templates/github/workflows/validate-task-system.yml` to `.github/workflows/validate-task-system.yml`.
7. Generate and validate the initial live instance:

   ```bash
   python .tasks/scripts/generate_index.py --instance-root .tasks
   python .tasks/scripts/validate.py --instance-only --instance-root .tasks
   ```

Routine validation in an adopting repository uses `--instance-only`. The complete installation contract is inside `.tasks/`; no root-level script or dependency file from this source repository is required.

## Product contents

```text
.tasks/
├── AGENTS.md
├── README.md
├── VERSION
├── config.yaml
├── index.yaml
├── requirements.txt
├── active/
├── archive/
├── schemas/
│   ├── config.schema.json
│   └── task.schema.json
├── scripts/
│   ├── generate_index.py
│   └── validate.py
└── templates/
    ├── AGENTS.md
    ├── github/workflows/validate-task-system.yml
    └── task/
```

## Source-repository development

For this repository, install dependencies and run:

```bash
python .tasks/scripts/generate_index.py --instance-root .project-tasks
python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks
```

New source-repository tasks are copied from `.tasks/templates/task/` into the active path configured in `.project-tasks/config.yaml`.

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

Correction loops:

```text
reviewing → implementing → testing → committing → reviewing
waiting_for_ci → implementing → testing → committing → reviewing → pushing → waiting_for_ci
awaiting_merge_approval → implementing → testing → committing → reviewing → pushing → waiting_for_ci
```

## Validation guarantees

The bundled validator checks:

- The pristine `.tasks/` product is self-contained and generic.
- Installed live instances are validated separately from pristine templates.
- No live task exists under the distributable active/archive directories.
- Live configurations and Markdown artifacts contain no unresolved placeholders.
- Configured paths resolve inside the intended template or live-instance root.
- Configurations and tasks satisfy the bundled JSON Schemas.
- Required active artifacts, screenshot directories, and configured archive artifacts exist.
- Complete lifecycle histories use connected, allowed transitions.
- Findings and plan approvals match current revisions and SHA-256 artifact digests.
- PR and merge approvals match the current production candidate; merge approval requires passed checks.
- Approval gates, acceptance criteria, and plan completion are satisfied before merge-related states.
- Acceptance criteria and plan steps remain traceable through their Markdown artifacts.
- The live generated index is current.
- No unresolved merge-conflict markers remain.

## Versioning

Version 3.0.0 introduces the self-contained `.tasks/` bundle and separate source-repository live state. Existing v1/v2 installations are not automatically migrated.

## License

MIT
