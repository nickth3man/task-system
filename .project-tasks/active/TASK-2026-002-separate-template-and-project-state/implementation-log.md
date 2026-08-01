# Implementation Log

## 2026-07-31T18:40:00-04:00 — Separate product and live state

### Commands

- GitHub repository inspection — confirmed the v2 tree and base commit.
- `python .tasks/scripts/generate_index.py --instance-root .project-tasks` — generated the live index.
- `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks` — passed before PR creation.

### Changes

- Made `.tasks/` generic and self-contained.
- Added bundled validators, index generation, dependencies, installation docs, root-instruction template, and workflow template.
- Added `.project-tasks/` as the live source-repository task instance.
- Updated schemas for explicit template/live modes.
- Updated root documentation, agent instructions, and CI.

### Discoveries

- Using the same root as both a pristine template and initialized live instance requires separate validation modes.
- Approval, lifecycle, path-containment, and artifact-contract rules need semantic checks beyond JSON Schema.

### Decisions and rejected alternatives

- Decision: adopting repositories use `.tasks/` as both product and live instance after initialization.
- Decision: only the task-system source repository uses `.project-tasks/`.
- Decision: version increased to 3.0.0 because distribution and configuration contracts changed.
- Rejected alternative: a separate export directory, because `.tasks/` must remain the canonical copyable product.
- Rejected alternative: keeping tools at repository root, because a copied `.tasks/` directory would be incomplete.

### Deviations, failures, and resolutions

- Plan deviation: None.
- Failure and resolution: None during initial implementation.

### Metrics or evidence

- Initial PR changed 48 files and introduced the complete `.tasks/` bundle plus `.project-tasks/` live state.
- GitHub Actions run `30671035619` passed on head `4959ed6c728bbaea00f46453c47353b648dc04fc` before review remediation.

## 2026-07-31T19:10:00-04:00 — Address all PR review findings

### Commands

- `python -m py_compile .tasks/scripts/validate.py .tasks/scripts/generate_index.py` — passed.
- `python .tasks/scripts/validate.py --template-only --template-root .tasks` — passed for the pristine bundle.
- `python .tasks/scripts/generate_index.py --instance-root .tasks` followed by `python .tasks/scripts/validate.py --instance-only --instance-root .tasks` — passed in a simulated installed repository.
- `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks` — passed for the source repository.
- Negative validation scenarios — confirmed clean failures for path escape, malformed YAML, unreplaced Markdown placeholders, missing screenshot directories, invalid lifecycle transitions, stale approval heads, and missing approval gates.

### Changes

- Added separate template-only and instance-only validation paths, including same-root mode auto-selection.
- Enforced resolved filesystem containment for configured paths.
- Enforced complete lifecycle transition graphs, approval gates, revision binding, candidate-head binding, merge checks, and acceptance evidence.
- Derived active, archive, and template artifact requirements from shared constants and live configuration.
- Required all Markdown templates and rejected live Markdown placeholders.
- Hardened index generation and malformed-input diagnostics.
- Restored repeatable acceptance/plan traceability and missing assessment/research guidance.

### Discoveries

- Recording approval against a commit that contains its own SHA is self-referential. The durable model must distinguish the reviewed production candidate from later task-record-only metadata commits.
- Archived artifact requirements must come from `archive.preserve`, not the active artifact set.

### Decisions and rejected alternatives

- Decision: `git.candidate_head_sha` is the approval-bound production candidate; metadata-only task-record commits do not replace it.
- Decision: adopters validate the pristine copy before changing `mode` to `live`, then use instance-only validation.
- Rejected alternative: weakening template checks when roots match, because explicit modes provide clearer installation and CI behavior.

### Deviations, failures, and resolutions

- Plan deviation: Review remediation expanded semantic validation within the approved dual-root scope.
- Failure and resolution: The initial same-root installation command imposed contradictory modes; resolved with `--template-only`, `--instance-only`, auto-selection, and corrected documentation/workflow commands.

### Metrics or evidence

- All Codex, CodeRabbit, Cubic, and Sourcery actionable findings were mapped to code or documentation changes.
- The final validation suite covers positive template/live flows and the reported negative cases.

## 2026-07-31T20:00:00-04:00 — Address second review pass

### Commands

- `python -m py_compile .tasks/scripts/validate.py .tasks/scripts/generate_index.py .tasks/tests/test_tools.py` — passed.
- `python -m unittest discover -s .tasks/tests -p "test_*.py" -v` — 8 regression tests passed locally and in GitHub Actions.
- `python .tasks/scripts/validate.py --template-root .tasks --instance-root .project-tasks` — passed after normalizing the generated template index.

### Changes

- Required merge approval, the recorded PR head, and the reviewed candidate head to reference the same commit.
- Rejected symlinked task records that resolve outside configured active or archive roots.
- Required non-empty schema and task-system versions before index generation.
- Made malformed list-valued IDs and plan references produce validation errors instead of `TypeError` crashes.
- Required the distributable index to equal the deterministic empty generated index.
- Replaced substring traceability checks with token-bounded AC and PLAN matching.
- Restricted blocked-task resumption to its recorded nonterminal resume state.
- Made `completed` terminal except for the normal `completed -> archived` transition.
- Added eight regression tests and ran them in both source-repository and adopter CI workflows.

### Discoveries

- The checked-in template index used quoted version strings, while deterministic generation emitted equivalent unquoted scalars; exact generated-view enforcement correctly detected the difference.
- Review invariants need executable regression tests in addition to semantic validation so future refactors cannot silently reintroduce the same edge cases.

### Decisions and rejected alternatives

- Decision: preserve exact generated-index formatting rather than accepting merely equivalent YAML.
- Decision: retain one shared regression suite inside the copyable `.tasks/` bundle and execute it in adopter CI.
- Rejected alternative: allowing blocked tasks to resume at arbitrary later states, because that bypasses mandatory lifecycle gates.

### Deviations, failures, and resolutions

- Plan deviation: None; the work is review-driven hardening within the approved validation scope.
- Failure and resolution: GitHub Actions run `30674627587` failed because `.tasks/index.yaml` was not byte-for-byte equal to the generated empty view. The index was regenerated in commit `ff5bbdeb076ba1f98d46afaa494c641f56f384a0`; run `30674658942` then passed.

### Metrics or evidence

- Eight targeted regression tests passed.
- All eight findings from the second Cubic review pass were addressed.
- Final reviewed production candidate: `ff5bbdeb076ba1f98d46afaa494c641f56f384a0`.
- Required workflow run `30674658942` passed.

## 2026-07-31T20:50:00-04:00 — Guard malformed blocker metadata

### Commands

- `python -m py_compile .tasks/scripts/validate.py .tasks/scripts/generate_index.py .tasks/tests/test_tools.py` — passed.
- `python -m unittest discover -s .tasks/tests -p "test_*.py" -v` — 9 regression tests passed.
- GitHub Actions workflow `Validate task system` run `30676496878` — passed after the temporary patch workflow was removed.

### Changes

- Guarded both terminal-state membership checks in `validate_blocker()` with `isinstance(value, str)` before set membership.
- Added `test_malformed_blocker_states_do_not_raise_type_error` with list- and mapping-valued blocker status fields.
- Removed the temporary one-shot workflow used to apply the exact patch to the PR branch.

### Discoveries

- The schema correctly reports non-string blocker values, but semantic validation continues to collect additional errors. Direct set membership therefore must not assume schema-valid or hashable values.

### Decisions and rejected alternatives

- Decision: preserve error accumulation and make the semantic check type-safe rather than returning early after schema errors.
- Rejected alternative: changing the terminal-state set to a sequence, because explicit type guards communicate the validation contract and avoid accidental equality checks on arbitrary objects.

### Deviations, failures, and resolutions

- Plan deviation: None; this is a review-driven robustness correction within the approved validator scope.
- Failure and resolution: The unguarded membership expression could raise `TypeError` for list or mapping values. Commit `c44a23a5cbe3a1b328584c87cf53e3900ebc1c27` adds the guards and regression test; cleanup commit `0aa95eea88f99c98fef59b6a38f6d44a5bfe6f02` removes temporary automation.

### Metrics or evidence

- Regression suite increased from 8 to 9 tests.
- The Cubic review thread was answered and resolved.
- Required workflow run `30676496878` passed.
