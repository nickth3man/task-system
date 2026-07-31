# AGENTS.md

## Project identity

- Project: `[PROJECT_NAME]`
- Purpose: `[ONE_SENTENCE_PURPOSE]`
- Primary language/runtime: `[LANGUAGE_AND_VERSION]`
- Default branch: `[DEFAULT_BRANCH]`
- Package/build system: `[PACKAGE_OR_BUILD_SYSTEM]`

## Repository architecture

Document the major directories, runtime boundaries, generated code, persistent data, public interfaces, and deployment units.

```text
[DIRECTORY_OR_COMPONENT] — [RESPONSIBILITY]
```

## Required development commands

Agents must discover and preserve the repository's established commands. Replace the placeholders below.

```text
Install:     [COMMAND]
Build:       [COMMAND]
Format:      [COMMAND]
Lint:        [COMMAND]
Type-check:  [COMMAND]
Unit tests:  [COMMAND]
Integration: [COMMAND]
End-to-end:  [COMMAND]
Run locally: [COMMAND]
```

If a command does not apply, state `Not applicable` and explain why.

## Coding conventions

- Follow existing style and architecture before introducing a new pattern.
- Keep changes scoped to the approved task.
- Preserve public compatibility unless the approved plan explicitly changes it.
- Do not introduce dependencies, generated files, migrations, or configuration changes without documenting them in the task plan.
- Add or update tests for changed behavior.
- Update documentation when behavior, configuration, APIs, or developer workflows change.

## Repository safety

- Never discard, overwrite, stash, commit, or absorb unrelated user changes.
- Never modify secrets, credentials, production data, or deployment settings unless the approved task explicitly requires it.
- Do not run destructive commands without explicit user authorization.
- Do not bypass tests, branch protection, required checks, or security controls.
- Stop and ask when repository state is ambiguous or unsafe.

## Dependencies and generated artifacts

Describe repository-specific policies for:

- Adding or upgrading dependencies
- Lockfiles
- Generated code
- Database migrations
- API or schema generation
- Vendored files
- Binary assets

## Git and GitHub conventions

- Follow the task branch and commit rules in `.tasks/AGENTS.md`.
- Repository-specific merge strategy: `[REPOSITORY_DEFAULT_OR_UNSPECIFIED]`.
- Required GitHub workflows: `[WORKFLOW_NAMES_OR_DISCOVERY_RULE]`.
- PR template or labels: `[POLICY_OR_NOT_APPLICABLE]`.
- Release-note requirement: `[POLICY_OR_NOT_APPLICABLE]`.

## Task system

All feature, bug-fix, refactor, performance, security, audit, research, documentation, dependency, data, UI/UX, and scaffolding work must use the lifecycle in `.tasks/AGENTS.md` unless `.tasks/config.yaml` contains an explicit repository override.

`task.yaml` is authoritative for task state. Task Markdown files provide the human-readable record and evidence. Repository rules in this file and lifecycle rules in `.tasks/AGENTS.md` are both mandatory. If they conflict, stop and ask the user rather than choosing silently.

## Repository-specific task overrides

List and explain any overrides represented in `.tasks/config.yaml`. Do not place machine-readable override values only in this prose.

- `[OVERRIDE]`: `[RATIONALE]`
