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
