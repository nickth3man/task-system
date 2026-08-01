# Task System Bundle

A copy-and-paste task-management system for Git repositories.

## Layout

Two directories, with one rule between them:

```text
.tasks/          the bundle — this product. Replaced wholesale on upgrade.
.project-tasks/  the live instance — your config, index, and task records.
```

Live task state never lives inside the bundle. That is what makes upgrading
safe: replace `.tasks/` with a newer bundle and your task records are untouched.
The validator enforces the separation.

## Install

Use `python` instead of `python3` on Windows.

1. Copy this `.tasks/` directory into the target repository.
2. Install validation dependencies:

   ```bash
   python3 -m pip install -r .tasks/requirements.txt
   ```

3. Initialize the live instance:

   ```bash
   python3 .tasks/scripts/init.py
   ```

   There is nothing to choose. `init.py` detects the repository name, default
   branch, and forge from `git`, writes `.project-tasks/config.yaml`, creates the
   active and archive directories, generates the index, appends the
   `## Task system` section to the repository's root `AGENTS.md`, and writes
   `.github/workflows/validate-task-system.yml`. Add `--dry-run` to see the plan
   first.

   Re-running it is safe. An existing `config.yaml` is kept exactly as it is, and
   `AGENTS.md` is only ever appended to — never replaced, whatever it already
   contains and however long it is. If the section is already present, nothing
   happens.

   When the repository had no `AGENTS.md`, init also writes `AGENTS.example.md`
   with the full scaffold — project identity, architecture, required commands,
   repository safety — as a reference to grow your own from.

   Flags supply data rather than change behavior: `--bundle-root`,
   `--instance-root`, `--repository-name`, `--default-branch`, `--timezone`,
   `--remote`, `--provider`, `--no-github-checks`, `--dry-run`. In a repository
   with no `origin` remote, pass `--provider github --default-branch main`
   explicitly, or detection will settle on a CI-less configuration.

4. Fill in `commands.lint`, `commands.typecheck`, and `commands.unit_test` in
   `.project-tasks/config.yaml`.
5. Validate:

   ```bash
   python3 .tasks/scripts/validate.py --instance-only --instance-root .project-tasks
   ```

Everything after this can be asked of an agent in plain language — "create a task
for X", "validate the task system", "upgrade the task system". `.tasks/AGENTS.md`
maps each request to the single command that serves it.

## The instruction file is validated

The repository's root `AGENTS.md` is the only discovery path, so the validator
checks that it stays current. It must exist, must not be empty, must reference
`.tasks/AGENTS.md` and the live instance directory, must not describe paths a
previous layout used, and must not state a task-system major version other than
the installed one. A stale pointer is worse than a missing one, because an agent
follows it confidently.

`upgrade.py` repairs the mechanical parts of this automatically.

## Repositories without pull-request checks

By default the lifecycle requires green GitHub checks before merge approval. If
the repository has no such checks — a different forge, or no CI at all — set
`repository.provider: "other"` or `github.enabled: false` in the live config, or
pass `--provider other` / `--no-github-checks` to `init.py`. Merge approval then
binds to the reviewed candidate head alone. Every other gate is unchanged.

## Start a task

```bash
python3 .tasks/scripts/new_task.py --slug fix-login-retry --title "Fix login retry backoff"
```

This allocates the next ID, copies the template, fills every mechanical field
(ID, slug, title, timestamps, repository, branch, actor), regenerates the index,
and prints exactly which placeholders still need content. Add `--type` to pick a
task type and `--original-request` to record the request verbatim.

Then write the remaining content, create every acceptance criterion and plan step
the task needs, and follow `.tasks/AGENTS.md`.

Every task type gets the same artifacts and the same approval gates. A section
that does not apply stays in place and explains why, so a record is never
ambiguous about what was considered.

## Upgrade

**Pre-4.0 installations keep live state inside `.tasks/`.** Do not delete or
replace `.tasks/` before running `upgrade.py`, or that state is lost.
`--bundle-root` names a single directory that must hold both the new bundle and
the legacy live state, so overlay the new bundle onto the existing `.tasks/`
without removing anything:

```bash
cp -R new-bundle/. .tasks/
```

A 4.0 bundle ships no `config.yaml`, `index.yaml`, `active/`, or `archive/`, so
the overlay leaves the live state untouched. Then run the upgrade with its
defaults:

```bash
python3 .tasks/scripts/upgrade.py --dry-run   # see the plan
python3 .tasks/scripts/upgrade.py
```

Once the upgrade completes, live state has moved to `.project-tasks/` and it is
safe to replace `.tasks/` outright with the new bundle.

4.0-or-later installations keep no live state in the bundle, so simply replace
`.tasks/` and re-run `upgrade.py`.

`upgrade.py` moves live state out of the bundle if a pre-4.0 installation kept it
there, adds configuration keys the new version requires, rewrites paths and
commands that pointed into the bundle, repairs the mechanical references in
`AGENTS.md`, bumps the recorded version, and regenerates the index. It never edits
task records and never changes a value you already set.

Upgrading from 4.x also removes the lite artifact profile. Any task record created
under it is missing `assessment.md`, `research.md`, `links.md`,
`implementation-log.md`, and `review.md`, and will fail validation until those
artifacts exist; `upgrade.py` does not write them for you.

Running it twice is a no-op. Comments in `config.yaml` are lost in the rewrite;
the previous file is kept as `config.yaml.bak`, so diff the two before committing.

Validate afterwards:

```bash
python3 .tasks/scripts/validate.py --instance-only --instance-root .project-tasks
```

## Validation

```bash
# the bundle, before or after installation
python3 .tasks/scripts/validate.py --template-only --template-root .tasks

# the live instance — this is the routine check, and what CI runs
python3 .tasks/scripts/validate.py --instance-only --instance-root .project-tasks

# regenerate the index after any task record changes
python3 .tasks/scripts/generate_index.py --instance-root .project-tasks
```

The validator reads only the bundle, the instance directory, and the configured
root-level instruction file. It does not scan the rest of the repository.
