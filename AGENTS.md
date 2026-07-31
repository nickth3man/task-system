# AGENTS.md

## Project identity

- Project: `task-system`
- Purpose: Maintain the reusable cross-project task lifecycle, schemas, templates, validation scripts, and installation guidance.
- Primary runtime: Python 3.11 or newer for validation tooling.
- Default branch: `main`
- Package management: `requirements-dev.txt`

## Repository architecture

```text
.tasks/AGENTS.md                  — lifecycle rules installed into projects
.tasks/config.yaml                — live configuration for this repository
.tasks/templates/config.yaml      — consumer configuration template
.tasks/templates/task/            — task artifact templates
.tasks/schemas/                    — JSON Schemas for configuration and task records
scripts/validate.py               — structural and semantic validator
scripts/generate_index.py         — deterministic task index generator
AGENTS.project-template.md        — root AGENTS.md template for adopting projects
README.md                         — installation and operating guide
```

## Required development commands

```text
Install:        python -m pip install -r requirements-dev.txt
Validate:       python scripts/validate.py
Generate index: python scripts/generate_index.py
Check index:    python scripts/generate_index.py --check
```

Formatting, linting, type-checking, unit tests, integration tests, end-to-end tests, and builds are not currently separate commands. `scripts/validate.py` is the required repository check.

## Coding and documentation conventions

- Keep the Markdown instructions, YAML templates, JSON Schemas, validators, and README behaviorally consistent.
- Treat lifecycle, required-schema, or required-artifact changes as major task-system versions.
- Treat new optional fields as minor versions and compatible wording corrections as patch versions.
- Update `.tasks/VERSION`, live configuration, templates, schemas, README, and validation expectations together when versioning changes.
- Keep generated `.tasks/index.yaml` deterministic; update it only with `scripts/generate_index.py`.
- Add semantic validation for rules that JSON Schema cannot express reliably.
- Use stable public schema identifiers under this repository rather than placeholder domains.

## Repository safety

- Follow `.tasks/AGENTS.md` for repository changes after the v2 bootstrap.
- Never modify or absorb unrelated work.
- Never weaken approval, CI, merge, or evidence requirements merely to make a record validate.
- Do not introduce destructive Git operations into templates or agent instructions.
- Preserve backward-compatibility guidance when a new major version changes existing task records.

## Git and GitHub conventions

- Task branches use `task/TASK-YYYY-NNN-kebab-case-slug`.
- Commits use `TASK-YYYY-NNN: concise imperative summary` when associated with a task.
- Pull requests must pass the `Validate task system` workflow.
- Follow repository policy for merge method; use squash when the policy is ambiguous.

## Task system

All independently mergeable changes to this repository use `.tasks/AGENTS.md`. `task.yaml` is authoritative for state; Markdown artifacts preserve evidence. If root instructions, lifecycle instructions, configuration, and repository behavior conflict, stop and resolve the conflict rather than choosing silently.
