# AGENTS.md

## Project identity

- Project: `__REQUIRED_PROJECT_NAME__`
- Purpose: `__REQUIRED_PROJECT_PURPOSE__`
- Primary language/runtime: `__REQUIRED_RUNTIME__`
- Default branch: `__REQUIRED_DEFAULT_BRANCH__`

## Architecture

Document the major directories, runtime boundaries, generated files, persistent data, public interfaces, and deployment units.

## Required commands

```text
Install:     __REQUIRED_INSTALL_COMMAND__
Build:       __REQUIRED_BUILD_COMMAND_OR_NOT_APPLICABLE__
Format:      __REQUIRED_FORMAT_COMMAND_OR_NOT_APPLICABLE__
Lint:        __REQUIRED_LINT_COMMAND_OR_NOT_APPLICABLE__
Type-check:  __REQUIRED_TYPECHECK_COMMAND_OR_NOT_APPLICABLE__
Unit tests:  __REQUIRED_UNIT_TEST_COMMAND_OR_NOT_APPLICABLE__
Integration: __REQUIRED_INTEGRATION_COMMAND_OR_NOT_APPLICABLE__
End-to-end:  __REQUIRED_E2E_COMMAND_OR_NOT_APPLICABLE__
```

## Repository safety

- Never discard, overwrite, stash, commit, or absorb unrelated user changes.
- Do not run destructive commands without explicit authorization.
- Preserve public compatibility unless the approved task changes it.
- Add or update tests and documentation for changed behavior.

## Task system

All independently mergeable work follows `.tasks/AGENTS.md` and uses the live configuration in `.project-tasks/config.yaml`. `task.yaml` is authoritative. If repository rules and task-system rules conflict, stop and ask rather than choosing silently.

`.tasks/` is the task-system bundle and is replaced wholesale on upgrade. Never store task records or repository-specific configuration inside it.
