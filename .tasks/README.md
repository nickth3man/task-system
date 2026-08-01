# Task System Bundle

This directory is a self-contained, copy-and-paste task-management system for Git repositories.

## Install

1. Copy the entire `.tasks/` directory into the target repository.
2. Install validation dependencies:

   ```bash
   python -m pip install -r .tasks/requirements.txt
   ```

3. Validate the untouched distributable bundle before initialization:

   ```bash
   python .tasks/scripts/validate.py --template-only --template-root .tasks
   ```

4. Initialize `.tasks/config.yaml` by replacing every `__REQUIRED_*__` value and changing `mode: template` to `mode: live`.
5. Copy `.tasks/templates/AGENTS.md` to the repository root as `AGENTS.md`, or merge its task-system section into an existing root file.
6. Copy `.tasks/templates/github/workflows/validate-task-system.yml` to `.github/workflows/validate-task-system.yml`.
7. Generate the initial live index and validate the initialized instance:

   ```bash
   python .tasks/scripts/generate_index.py --instance-root .tasks
   python .tasks/scripts/validate.py --instance-only --instance-root .tasks
   ```

After initialization, `.tasks/` is the repository's live task instance. Use `--instance-only` for routine validation. The validator also auto-selects template or live validation when the template and instance roots are the same and `mode` is unambiguous.

## Start a task

Copy `.tasks/templates/task/` into `.tasks/active/TASK-YYYY-NNN-slug/`, replace all required placeholders, create every acceptance criterion and plan step needed for the task, and follow `.tasks/AGENTS.md`.

## Special source-repository layout

The `nickth3man/task-system` source repository intentionally keeps this directory generic. Its own live task records are stored under `.project-tasks/`. Adopting projects normally use `.tasks/` as both the installed system and live task instance.
