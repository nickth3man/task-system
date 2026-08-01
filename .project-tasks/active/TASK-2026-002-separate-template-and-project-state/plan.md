# Implementation Plan

- Task: `TASK-2026-002`
- Plan revision: `1`
- Findings revision used: `1`
- Approval status: Approved by the user's instruction to create the plan and update GitHub

## PLAN-01 — Make `.tasks/` self-contained and generic

Supports: `AC-01`, `AC-05`

Files and symbols:
- `.tasks/config.yaml`
- `.tasks/README.md`
- `.tasks/requirements.txt`
- `.tasks/scripts/`
- `.tasks/templates/AGENTS.md`
- `.tasks/templates/github/workflows/validate-task-system.yml`

Method:
- Replace repository-specific configuration with required placeholders.
- Move validation/index tooling and dependencies into `.tasks/`.
- Include installation instructions and copyable root/workflow templates.
- Ensure `.tasks/active` and `.tasks/archive` contain no real tasks.

Validation:
- Run template validation and inspect the complete `.tasks/` tree.

Risks and mitigation:
- Placeholder configuration cannot be validated as a live instance; validate it in explicit template mode.

Migration or rollback:
- Revert the PR to restore the v2 layout.

## PLAN-02 — Add the live `.project-tasks/` instance

Supports: `AC-02`

Files and symbols:
- `.project-tasks/config.yaml`
- `.project-tasks/index.yaml`
- `.project-tasks/active/TASK-2026-002-separate-template-and-project-state/`
- `AGENTS.md`

Method:
- Configure live paths under `.project-tasks/` while reusing `.tasks/templates/task`.
- Bootstrap this migration as the first live task record.
- Make root instructions prohibit live state in `.tasks/`.

Validation:
- Validate `.project-tasks/` against schemas in `.tasks/` and verify its generated index.

Risks and mitigation:
- Bootstrap circularity is documented in the task record; subsequent changes must follow the normal lifecycle without exception.

Migration or rollback:
- Remove `.project-tasks/` and restore v2 root paths.

## PLAN-03 — Generalize validation and index generation

Supports: `AC-03`

Files and symbols:
- `.tasks/scripts/validate.py`
- `.tasks/scripts/generate_index.py`
- `.tasks/schemas/config.schema.json`
- `.tasks/schemas/task.schema.json`

Method:
- Add `--template-root` and `--instance-root` arguments.
- Validate generic-template invariants separately from live-instance invariants.
- Generate indexes from configured paths.
- Reject live tasks in the distributable bundle and placeholders in live state.

Validation:
- Run the validator against `.tasks/` plus `.project-tasks/`.
- Run index generation in check mode.

Risks and mitigation:
- Path resolution errors are mitigated by repository-relative normalization and CI execution.

Migration or rollback:
- Revert to root-level v2 scripts.

## PLAN-04 — Update CI and documentation

Supports: `AC-04`, `AC-05`

Files and symbols:
- `.github/workflows/validate.yml`
- `README.md`
- `AGENTS.md`

Method:
- Install dependencies from `.tasks/requirements.txt`.
- Run bundled validation against both roots.
- Explain product/live boundaries and normal adoption behavior.

Validation:
- GitHub workflow `Validate task system` passes on the PR.

Risks and mitigation:
- CI path regressions are caught before merge.

Migration or rollback:
- Restore the v2 workflow and documentation.

## Commit strategy

1. `TASK-2026-002: separate template and live task state`
2. `TASK-2026-002: record PR and CI metadata` when required
