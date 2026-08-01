# Verification

## AC-01 — Generic distributable bundle

- Status: Passed
- Procedure: Validate the untouched `.tasks/` bundle with `--template-only`, inspect its generic configuration, confirm that distributable active/archive paths contain no real tasks, and verify that its index is the exact deterministic empty generated view.
- Actual: The pristine bundle passes and contains all bundled scripts, dependencies, schemas, templates, tests, and required directories.

## AC-02 — Self-governing source repository

- Status: Passed
- Evidence: `.project-tasks/config.yaml`, the live `TASK-2026-002` record, and root `AGENTS.md` direct source-repository work to `.project-tasks/`.

## AC-03 — Dual-root validation

- Status: Passed
- Commands:
  - `python .tasks/scripts/validate.py --template-only --template-root .tasks`
  - `python .tasks/scripts/validate.py --instance-only --instance-root .tasks` in a simulated initialized installation
  - `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks`
  - `python -m unittest discover -s .tasks/tests -p "test_*.py" -v`
- Actual: Template-only, instance-only, same-root, and source-repository dual-root flows passed; all eight validator/index regression tests passed.
- Negative cases: path escape, symlink escape, missing versions, malformed YAML and list-valued IDs, Markdown placeholders, missing screenshots, prefix-sharing AC/PLAN references, invalid lifecycle transitions, blocked-state jumps, stale approval heads/revisions, and missing approval gates all failed cleanly as expected.

## AC-04 — CI enforcement

- Status: Passed
- Evidence:
  - GitHub Actions run `30674627587` correctly failed when exact template-index validation detected a stale generated view.
  - After regeneration, GitHub Actions run `30674658942` passed on production candidate `ff5bbdeb076ba1f98d46afaa494c641f56f384a0`.
  - The source and adopter workflow templates both execute the regression suite before semantic validation.

## AC-05 — Clear installation path

- Status: Passed
- Evidence: `README.md`, `.tasks/README.md`, `.tasks/config.yaml`, `.tasks/templates/AGENTS.md`, and `.tasks/templates/github/workflows/validate-task-system.yml` describe the pristine validation, live initialization, index generation, regression-test, and instance-only CI flow.

## Known failures

- None. The intermediate stale-index failure was corrected and the final required workflow passed.

## Skipped checks

- None.
