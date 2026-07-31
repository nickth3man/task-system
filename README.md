# Cross-Project Task System

A repository-local, AI-agent-friendly workflow for taking one independently mergeable unit of work from intake through assessment, research, findings, planning, implementation, verification, review, CI, merge, and durable archival.

## Two roles in this source repository

This repository deliberately separates the **task-system product** from the **task records used to develop the product**.

```text
.tasks/          distributable product; copy this directory into another repository
.project-tasks/  live task instance for nickth3man/task-system itself
```

The `.tasks/` directory must remain generic. It contains no real active or archived tasks and no configuration initialized for this repository. All changes to the task-system product are governed by live task records under `.project-tasks/`.

Adopting repositories normally do not need `.project-tasks/`: after copying `.tasks/`, they use `.tasks/` as both the installed product and live task instance.

## Copy-and-paste installation

1. Copy the entire `.tasks/` directory into the target repository.
2. Replace every `__REQUIRED_*__` value in `.tasks/config.yaml`.
3. Copy `.tasks/templates/AGENTS.md` to the target repository root as `AGENTS.md`, or merge its task-system section into an existing root file.
4. Copy `.tasks/templates/github/workflows/validate-task-system.yml` to `.github/workflows/validate-task-system.yml`.
5. Install the bundled dependencies:

   ```bash
   python -m pip install -r .tasks/requirements.txt
   ```

6. Generate and validate the initial live index:

   ```bash
   python .tasks/scripts/generate_index.py --instance-root .tasks
   python .tasks/scripts/validate.py --instance-root .tasks
   ```

The complete installation contract is inside `.tasks/`; no root-level script or dependency file from this source repository is required.

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
```

## Validation guarantees

The bundled validator checks:

- The `.tasks/` product is self-contained and generic.
- No live task exists under the distributable active/archive directories.
- Live configurations contain no unresolved placeholders.
- Configurations and tasks satisfy the bundled JSON Schemas.
- Required task artifacts exist.
- Task IDs, acceptance criteria, and plan-step references are consistent.
- Findings and plan approvals match SHA-256 artifact digests.
- Active/archive placement agrees with task status.
- The live generated index is current.
- No unresolved merge-conflict markers remain.

## Versioning

Version 3.0.0 introduces the self-contained `.tasks/` bundle and separate source-repository live state. Existing v1/v2 installations are not automatically migrated.

## License

MIT
