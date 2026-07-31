# Findings

- Task: `TASK-2026-002`
- Findings revision: `1`
- Approval status: Approved in chat

## Executive conclusion

The repository needs two distinct roots: `.tasks/` as the generic, copyable product and `.project-tasks/` as the live instance governing development of that product.

## FIND-01 — Current `.tasks/` is not a standalone template

Evidence:
- `.tasks/config.yaml` is initialized for `task-system`.
- Required validators and dependency declarations live outside `.tasks/`.
- Root instructions treat `.tasks/active` as live source-repository state.

Conclusion:
- Copying `.tasks/` does not currently produce a complete generic installation.

## FIND-02 — A configurable instance root resolves the conflict

Evidence:
- Templates and schemas are reusable independently of active/archive state.
- Active/archive/index paths already exist in configuration and can point to `.project-tasks/`.

Conclusion:
- Bundled tools should accept an explicit live-instance root while loading product schemas and templates from `.tasks/`.

## Options considered

1. Keep `.tasks/` live and add a separate export directory — rejected because `.tasks/` would still not be the canonical copyable product.
2. Store product files in another directory and keep `.tasks/` live — rejected because the user explicitly requires `.tasks/` to remain the copy-and-pasteable template.
3. Use `.tasks/` as product and `.project-tasks/` as live state — selected.

## Recommended direction

Move all portable runtime pieces into `.tasks/`, make `.tasks/config.yaml` generic, create `.project-tasks/config.yaml` for this repository, and update validation/CI to enforce both roles.

## Risks and open questions

- Major-version migration guidance must clearly state that prior installed repositories retain the normal `.tasks/` live layout.
