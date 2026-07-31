# TASK-2026-002 — Separate distributable template from project task state

## Original request

> I would like this repo to be used to work on and modify the task system. The repo should be held to the task system rules as well, while the copy-and-pasteable task system template (`.tasks`) remains a template. The `task-system` project should not itself be the system stored in `.tasks`; `.tasks` must be directly reusable in any project.

## Objective

Separate the reusable `.tasks/` product from the live task records used to develop `nickth3man/task-system`, while continuing to enforce the same lifecycle on changes to the task-system product.

## Scope

### In scope

- Make `.tasks/` a generic, self-contained bundle with no repository-specific live state.
- Add `.project-tasks/` as the live task instance for this repository.
- Move validation, index generation, dependencies, installation instructions, and project templates into `.tasks/`.
- Update CI, root instructions, and repository documentation for the two-root model.
- Add validation that prevents live tasks or `task-system`-specific configuration from entering the distributable bundle.

### Out of scope

- Building a compiled CLI.
- Automatically installing the bundle into other repositories.
- Migrating external repositories that already copied v1 or v2.

## Constraints

- `.tasks/` must be copyable as one directory and contain the files needed to install and validate the system.
- Changes to `.tasks/` in this repository must be governed by task records under `.project-tasks/`.
- Existing approval, CI, review, and archival rules remain intact.

## Acceptance criteria

### AC-01 — Generic distributable bundle

`.tasks/` contains no live task records or `task-system`-specific repository configuration and can be copied into another repository as the complete task-system bundle.

### AC-02 — Self-governing source repository

The `task-system` repository stores its live active/archive state under `.project-tasks/` and root instructions require all future changes to use that instance.

### AC-03 — Dual-root validation

The bundled validator can independently validate the generic `.tasks/` template and a live task instance at a configurable path.

### AC-04 — CI enforcement

GitHub Actions validates both the distributable template and `.project-tasks/`, including generated-index consistency.

### AC-05 — Clear installation path

Documentation explains how adopters copy `.tasks/`, initialize its configuration, install dependencies, add root instructions/workflow, and validate the installation.
