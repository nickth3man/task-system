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
   python3 .tasks/scripts/init.py
   ```

   There is nothing to configure. It writes the live instance, appends the
   `## Task system` section to the root `AGENTS.md` without disturbing anything
   already there, and installs the validation workflow. Re-running it never
   overwrites your configuration or instructions.

4. Fill in the lint, type-check, and test commands in
   `.project-tasks/config.yaml`.
5. Validate:

   ```bash
   python3 .tasks/scripts/validate.py --instance-only --instance-root .project-tasks
   ```

From here on, ask an agent in plain language — "create a task for X", "validate
the task system" — and `.tasks/AGENTS.md` tells it exactly what to run.

`.tasks/README.md` documents the no-CI configuration and the upgrade procedure.
The complete installation contract is inside `.tasks/`; no root-level script or
dependency file from this repository is required.

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

Version 5.0.0 removes every variant from the system. The lite artifact profile
and `lifecycle.lite_profile_task_types` are gone — one artifact set applies to
every task type. `init.py` keeps only flags that supply data: the behavior
toggles `--force`, `--install-root-agents`, `--instruction-file`,
`--install-workflow`, and `--prune-install-files` are removed, the root
`AGENTS.md` is always appended to and never replaced, and the validation workflow
is always installed. A record created under the 4.x lite profile is missing five
artifacts and will fail validation until they exist.

Version 4.0.0 separated the replaceable bundle from live state in every
installation, added `scripts/init.py`, `scripts/new_task.py`, and
`scripts/upgrade.py`, added `paths.bundle` and `paths.instructions` to the
configuration, validated the agent instruction file, and made the pull-request
check gate conditional on `repository.provider` and `github.enabled`. Upgrade any
installation by replacing the bundle and running
`python3 .tasks/scripts/upgrade.py`. Version 3.0.0 introduced the self-contained
`.tasks/` bundle. Existing v1/v2 installations are not automatically migrated.

## License

MIT
