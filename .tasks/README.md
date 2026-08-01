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
   python3 .tasks/scripts/init.py --install-root-agents --install-workflow
   ```

   `init.py` detects the repository name, default branch, and forge from `git`,
   writes `.project-tasks/config.yaml`, creates the active and archive
   directories, and generates the index. Add `--dry-run` to see what it would do
   first. Useful flags:

   | Flag | Effect |
   | --- | --- |
   | `--instance-root DIR` | Put live state somewhere other than `.project-tasks/` |
   | `--bundle-root DIR` | The bundle is somewhere other than `.tasks/` |
   | `--instruction-file PATH` | The file your agent reads: `CLAUDE.md`, `.github/copilot-instructions.md`, … |
   | `--timezone AREA/CITY` | IANA timezone; defaults to `UTC` |
   | `--provider other` / `--no-github-checks` | No pull-request check gate (see below) |
   | `--prune-install-files` | Delete install-only files from the bundle afterwards |

   `--install-root-agents` never destroys an existing instruction file. If one is
   present it appends the `## Task system` section; if that section is already
   there it does nothing. Only `--force` replaces the file wholesale.

4. Replace any remaining `__REQUIRED_*` values in the instruction file, and fill
   in `commands.lint`, `commands.typecheck`, and `commands.unit_test` in
   `.project-tasks/config.yaml`.
5. Validate:

   ```bash
   python3 .tasks/scripts/validate.py --instance-only --instance-root .project-tasks
   ```

## The instruction file is validated

`paths.instructions` records which repository-root file points agents at the task
system — it is the only discovery path, so the validator checks that it stays
current. It must exist, must not be empty, must reference `.tasks/AGENTS.md` and
the live instance directory, must not describe paths a previous layout used, and
must not state a task-system major version other than the installed one. A stale
pointer is worse than a missing one, because an agent follows it confidently.

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

### Lite profile

`lifecycle.lite_profile_task_types` lists task types that require a reduced
artifact set — `task.yaml`, `task.md`, `findings.md`, `plan.md`,
`verification.md`, `completion.md` — with assessment and research folded into
`findings.md`. It ships set to `["documentation", "dependency"]`. Every approval,
gate, and traceability rule is unchanged; only the file count drops. Set it to
`[]` to require the full profile everywhere.

## Upgrade

Replace the `.tasks/` directory with the newer bundle, then:

```bash
python3 .tasks/scripts/upgrade.py --dry-run   # see the plan
python3 .tasks/scripts/upgrade.py
```

`upgrade.py` moves live state out of the bundle if a pre-4.0 installation kept it
there, adds configuration keys the new version requires, rewrites paths and
commands that pointed into the bundle, repairs the mechanical references in the
instruction file, bumps the recorded version, and regenerates the index. It never
edits task records and never changes a value you already set — where a new key's
safe upgrade value differs from the shipped default it uses the conservative one,
so an existing installation is not opted into the lite profile behind your back.

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

The validator reads only the bundle and the instance directory. It does not scan
the rest of the repository.
