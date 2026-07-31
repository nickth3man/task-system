# Assessment

## Repository baseline

Version 2 treats `.tasks/` as both the distributable product and the live task instance. The root README calls `.tasks/config.yaml` the live repository configuration, root `AGENTS.md` directs changes to `.tasks/AGENTS.md`, root-level scripts implement validation/index generation, and the current `.tasks/config.yaml` is initialized for `task-system`.

This means copying `.tasks/` carries repository-specific configuration while omitting root-level scripts, dependency declarations, and the project `AGENTS.md` template. The directory is therefore not a self-contained copy-and-paste product.

## Expected behavior

`.tasks/` remains a pristine, self-contained product bundle. The task-system source repository governs its own changes through a separate live `.project-tasks/` instance. Adopters validate the pristine bundle, initialize it as `mode: live`, and then validate it with an instance-only command.

## Files inspected

| Path | Observation |
|---|---|
| `README.md` | Describes `.tasks/` as live state and requires copying files outside it. |
| `AGENTS.md` | Directs this repository to use `.tasks/` as its live instance. |
| `.tasks/config.yaml` | Contains `repository.name: task-system`. |
| `.tasks/AGENTS.md` | Hardcodes `.tasks/active` and `.tasks/archive` in several lifecycle instructions. |
| `scripts/validate.py` | Root-level tool, so it is not included when copying `.tasks/`. |
| `scripts/generate_index.py` | Root-level tool and tied to the current `.tasks` instance. |
| `.github/workflows/validate.yml` | Installs root dependency file and calls root validator. |

## Commands run

| Command | Purpose | Result |
|---|---|---|
| GitHub repository inspection | Confirm current structure and latest merged state | Version 2 is on `main` at `8b2ed41390840f57ad7cf15aa80d73435d454f29`. |
| `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks` | Validate the proposed two-root layout | Passed before PR creation. |

## Important code locations

- `.tasks/`: distributable task-system product after this change.
- `.project-tasks/`: live task state for the source repository.
- `.tasks/scripts/validate.py`: shared validator for template and live instances.
- `.tasks/scripts/generate_index.py`: configurable live-index generator.

## Existing tests and validation paths

- Local validator command: `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks`.
- Index check: `python .tasks/scripts/generate_index.py --instance-root .project-tasks --check`.
- GitHub Actions check: `Validate task system`.

## Assumptions

- Adopting repositories normally use `.tasks/` as both the installed bundle and live instance after initialization.
- Only the task-system source repository needs a separate `.project-tasks/` live root.

## Risks

- A path-generalization bug could validate the wrong task root.
- Maintaining both generic and live configuration could drift without CI checks.
- This is a breaking distribution-layout change and requires a major version bump.
