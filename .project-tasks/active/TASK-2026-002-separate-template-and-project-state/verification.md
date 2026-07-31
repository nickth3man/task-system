# Verification

## AC-01 — Generic distributable bundle

- Status: Passed
- Procedure: Validate the untouched `.tasks/` bundle with `--template-only`, inspect its generic configuration, and confirm that distributable active/archive paths contain no real tasks.
- Actual: The pristine bundle passes and contains all bundled scripts, dependencies, schemas, templates, and required directories.

## AC-02 — Self-governing source repository

- Status: Passed
- Evidence: `.project-tasks/config.yaml`, the live `TASK-2026-002` record, and root `AGENTS.md` direct source-repository work to `.project-tasks/`.

## AC-03 — Dual-root validation

- Status: Passed
- Commands:
  - `python .tasks/scripts/validate.py --template-only --template-root .tasks`
  - `python .tasks/scripts/validate.py --instance-only --instance-root .tasks` in a simulated initialized installation
  - `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks`
- Actual: Template-only, instance-only, same-root, and source-repository dual-root flows passed.
- Negative cases: path escape, malformed YAML, Markdown placeholders, missing screenshots, invalid transitions, stale approval heads/revisions, and missing approval gates all failed cleanly as expected.

## AC-04 — CI enforcement

- Status: Passed
- Evidence: GitHub Actions run `30672665593` passed on production candidate `e126fe42680b04d4a7cb33e0d7a7cdfad3b83d15`.

## AC-05 — Clear installation path

- Status: Passed
- Evidence: `README.md`, `.tasks/README.md`, `.tasks/config.yaml`, `.tasks/templates/AGENTS.md`, and `.tasks/templates/github/workflows/validate-task-system.yml` describe the pristine validation, live initialization, index generation, and instance-only CI flow.

## Known failures

- None.

## Skipped checks

- None.
