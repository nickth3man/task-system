# AGENTS.md

## Project identity

- Project: `task-system`
- Purpose: Maintain the reusable cross-project task lifecycle, templates, schemas, validation tools, and installation guidance.
- Primary runtime: Python 3.11 or newer.
- Default branch: `main`

## Repository architecture

```text
.tasks/                          — distributable product; copy this directory into other projects
.tasks/AGENTS.md                 — generic lifecycle rules installed with the product
.tasks/config.yaml               — generic, uninitialized consumer configuration
.tasks/scripts/                  — bundled validator and index generator
.tasks/schemas/                  — bundled JSON Schemas
.tasks/templates/                — task, root AGENTS.md, and GitHub workflow templates
.project-tasks/                  — live task instance for developing this repository
.project-tasks/config.yaml       — repository-specific live configuration
.project-tasks/active/           — active source-repository task records
.project-tasks/archive/          — archived source-repository task records
README.md                        — product and source-repository documentation
```

## Non-negotiable product/live boundary

- `.tasks/` is the copy-and-pasteable task-system product.
- Never create live task records under `.tasks/active/` or `.tasks/archive/` in this repository.
- Never initialize `.tasks/config.yaml` with `task-system` repository values.
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

Validate template and live instance:
python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks
```

## Development rules

- Follow `.tasks/AGENTS.md`, using `.project-tasks/config.yaml` as the live configuration.
- Keep generic product behavior in `.tasks/`; keep repository-specific state in `.project-tasks/` and this root file.
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
