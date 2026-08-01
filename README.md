# Cross-Project Task System

A repository-local, AI-agent-friendly workflow for taking one independently mergeable unit of work from intake through assessment, research, findings, planning, implementation, verification, review, CI, merge, and durable archival.

## Bundle and instance

Every installation, including this repository, has the same two directories:

```text
.tasks/          the bundle — the product. Replaced wholesale on upgrade.
.project-tasks/  the live instance — config, index, and task records.
```

Live task state never lives inside the bundle, so upgrading is a directory
replacement rather than a merge. The validator enforces the separation, and this
repository is an ordinary installation of its own product — there is no special
source-repository layout.

## Copy-and-paste installation

Use `python` instead of `python3` on Windows.

1. Copy the entire `.tasks/` directory into the target repository.
2. Install the bundled dependencies:

   ```bash
   python3 -m pip install -r .tasks/requirements.txt
   ```

3. Initialize the live instance:

   ```bash
   python3 .tasks/scripts/init.py --install-root-agents --install-workflow
   ```

4. Replace the remaining `__REQUIRED_*` values in the generated root `AGENTS.md`
   and fill in the lint, type-check, and test commands in
   `.project-tasks/config.yaml`.
5. Validate:

   ```bash
   python3 .tasks/scripts/validate.py --instance-only --instance-root .project-tasks
   ```

`.tasks/README.md` documents the installer flags, the no-CI configuration, and
the upgrade procedure. The complete installation contract is inside `.tasks/`;
no root-level script or dependency file from this repository is required.

## Product contents

```text
.tasks/
├── AGENTS.md
├── README.md
├── VERSION
├── requirements.txt
├── schemas/
│   ├── config.schema.json
│   └── task.schema.json
├── scripts/
│   ├── generate_index.py
│   ├── init.py
│   ├── new_task.py
│   ├── upgrade.py
│   └── validate.py
├── templates/
│   ├── AGENTS.md
│   ├── github/workflows/validate-task-system.yml
│   ├── instance/config.yaml
│   └── task/
└── tests/
```

## Developing this repository

```bash
python .tasks/scripts/generate_index.py --instance-root .project-tasks
python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks
python -m unittest discover -s .tasks/tests -p "test_*.py"
```

New tasks are created with `python .tasks/scripts/new_task.py --slug <slug>
--title "<title>"`, which writes into the active path configured in
`.project-tasks/config.yaml`.

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

- The pristine `.tasks/` bundle is self-contained and generic.
- Installed live instances are validated separately from the pristine bundle.
- The bundle contains no live configuration, index, or task records.
- Live configurations and Markdown artifacts contain no unresolved placeholders.
- Configured live-state paths resolve inside the instance root and outside the bundle.
- Configurations and tasks satisfy the bundled JSON Schemas.
- Required active artifacts, screenshot directories, and configured archive artifacts exist.
- Complete lifecycle histories use connected, allowed transitions.
- Findings and plan approvals match current revisions and SHA-256 artifact digests.
- PR and merge approvals match the current production candidate; merge approval requires passed checks where the repository has them.
- Approval gates, acceptance criteria, and plan completion are satisfied before merge-related states.
- Acceptance criteria and plan steps remain traceable through their Markdown artifacts.
- The live generated index is current.
- The configured agent instruction file exists, points at the installed bundle and instance, and does not describe a superseded layout or major version.
- No unresolved merge-conflict markers remain inside the bundle or the instance.

## Versioning

Version 4.0.0 separates the replaceable bundle from live state in every
installation, adds `scripts/init.py`, `scripts/new_task.py`, and `scripts/upgrade.py`, adds
`paths.bundle` and `paths.instructions` to the configuration, validates the agent
instruction file, adds the `lifecycle.lite_profile_task_types` profile, and makes
the pull-request check gate conditional on `repository.provider` and
`github.enabled`. Upgrade a 3.x installation by replacing the bundle and running
`python3 .tasks/scripts/upgrade.py`. Version 3.0.0 introduced the self-contained
`.tasks/` bundle. Existing v1/v2 installations are not automatically migrated.

## License

MIT
