# AGENTS.md

## Project identity

- Project: `task-system`
- Purpose: Maintain the reusable cross-project task lifecycle, templates, schemas, validation tools, and installation guidance.
- Primary runtime: Python 3.11 or newer.
- Default branch: `main`

## Repository architecture

```text
.tasks/                          — the bundle; copy this directory into other projects
.tasks/AGENTS.md                 — generic lifecycle rules installed with the bundle
.tasks/scripts/                  — initializer, task creator, upgrader, validator, and index generator
.tasks/schemas/                  — bundled JSON Schemas
.tasks/templates/                — task, instance config, root AGENTS.md, and workflow templates
.tasks/tests/                    — regression tests for the bundled tools
.project-tasks/                  — live task instance for this repository
.project-tasks/config.yaml       — repository-specific live configuration
.project-tasks/active/           — active task records
.project-tasks/archive/          — archived task records
README.md                        — product and development documentation
```

This repository is an ordinary installation of its own product. The layout above
is the layout every adopting repository gets; nothing here is special-cased.

## Non-negotiable bundle/instance boundary

- `.tasks/` is the copy-and-pasteable bundle and is replaced wholesale on upgrade.
- Never place live configuration, an index, or task records inside `.tasks/`.
- All changes to this repository, including changes inside `.tasks/`, are governed by the live instance in `.project-tasks/`.
- Create new tasks from `.tasks/templates/task/` but store them under the active path configured by `.project-tasks/config.yaml`.

## Required commands

```text
Install validation dependencies:
python -m pip install -r .tasks/requirements.txt

Generate live index:
python .tasks/scripts/generate_index.py --instance-root .project-tasks

Check live index:
python .tasks/scripts/generate_index.py --instance-root .project-tasks --check

Create a task:
python .tasks/scripts/new_task.py --slug <slug> --title "<title>"

Run bundled regression tests:
python -m unittest discover -s .tasks/tests -p "test_*.py"

Validate bundle and live instance:
python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks
```

## Development rules

- Follow `.tasks/AGENTS.md`, using `.project-tasks/config.yaml` as the live configuration.
- Keep generic product behavior in `.tasks/`; keep repository-specific state in `.project-tasks/` and this root file.
- The bundle must never reference this repository by name, owner, or URL.
- Update template documentation, schemas, scripts, examples, and validation together when behavior changes.
- Treat required lifecycle, schema, layout, or installation changes as major task-system versions.
- Keep `.project-tasks/index.yaml` generated and deterministic.
- Add semantic validation for rules JSON Schema cannot enforce.
- Do not weaken approval, CI, evidence, or merge gates merely to make records validate.

## Git and GitHub

- Task branches use `task/TASK-YYYY-NNN-kebab-case-slug`.
- Task commits use `TASK-YYYY-NNN: concise imperative summary`.
- Pull requests must pass `Validate task system`.
- The user approves findings, plan, PR creation, and implementation merge in chat.
- Use the repository's merge policy; use squash when multiple allowed methods are otherwise ambiguous.
