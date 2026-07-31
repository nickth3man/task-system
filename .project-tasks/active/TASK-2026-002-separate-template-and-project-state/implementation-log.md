# Implementation Log

## 2026-07-31T18:40:00-04:00 — Separate product and live state

State: `implementing`

Changes:
- Made `.tasks/` generic and self-contained.
- Added bundled validators, index generation, dependencies, installation docs, root-instruction template, and workflow template.
- Added `.project-tasks/` as the live source-repository task instance.
- Updated schemas for explicit template/live modes.
- Updated root documentation, agent instructions, and CI.

Decisions:
- Adopting repositories use `.tasks/` as both product and live instance.
- Only the task-system source repository uses `.project-tasks/`.
- Version increased to 3.0.0 because distribution and configuration contracts changed.

Rejected alternatives:
- Separate export directory: rejected because `.tasks/` must remain the canonical copyable product.
- Keep tools at repository root: rejected because a copied `.tasks/` directory would be incomplete.

Plan deviation:
- None.

Failures and resolution:
- None during local construction.
