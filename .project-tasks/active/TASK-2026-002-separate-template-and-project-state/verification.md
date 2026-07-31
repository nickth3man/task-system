# Verification

## AC-01 — Generic distributable bundle

- Status: Passed
- Procedure: Inspect `.tasks/` and run template validation.
- Actual: Generic placeholders remain in `.tasks/config.yaml`; `.tasks/active` and `.tasks/archive` contain no real tasks; all runtime files are inside `.tasks/`.

## AC-02 — Self-governing source repository

- Status: Passed
- Evidence: `.project-tasks/config.yaml`, live bootstrap task, and root `AGENTS.md` all point development work to `.project-tasks/`.

## AC-03 — Dual-root validation

- Status: Passed
- Command: `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks`
- Actual: Passed locally.

## AC-04 — CI enforcement

- Status: Passed
- Evidence: GitHub Actions run `30670947117` completed successfully for PR #2.

## AC-05 — Clear installation path

- Status: Passed
- Evidence: `README.md`, `.tasks/README.md`, `.tasks/templates/AGENTS.md`, and the bundled workflow template.

## Local command results

| Command | Result |
|---|---|
| `python -m pip install -r .tasks/requirements.txt` | Passed in validation environment |
| `python .tasks/scripts/generate_index.py --instance-root .project-tasks` | Passed |
| `python .tasks/scripts/generate_index.py --instance-root .project-tasks --check` | Passed |
| `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks` | Passed |

## Known failures

- None.

## Skipped checks

- None.
