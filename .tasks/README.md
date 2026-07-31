# Task System Bundle

This directory is a self-contained, copy-and-paste task-management system for Git repositories.

## Install

1. Copy the entire `.tasks/` directory into the target repository.
2. Replace every `__REQUIRED_*__` value in `.tasks/config.yaml`.
3. Copy `.tasks/templates/AGENTS.md` to the repository root as `AGENTS.md`, or merge its task-system section into an existing root file.
4. Copy `.tasks/templates/github/workflows/validate-task-system.yml` to `.github/workflows/validate-task-system.yml`.
5. Install validation dependencies:

   ```bash
   python -m pip install -r .tasks/requirements.txt
   ```

6. Validate the installation:

   ```bash
   python .tasks/scripts/validate.py --instance-root .tasks
   ```

## Start a task

Copy `.tasks/templates/task/` into `.tasks/active/TASK-YYYY-NNN-slug/`, replace all required placeholders, and follow `.tasks/AGENTS.md`.

## Special source-repository layout

The `nickth3man/task-system` source repository intentionally keeps this directory generic. Its own live task records are stored under `.project-tasks/`. Adopting projects normally use `.tasks/` as both the installed system and live task instance.
