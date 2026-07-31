# Research

## Questions

1. Is external research needed to determine the correct separation?
2. Can the desired behavior be derived from the repository's own lifecycle and packaging requirements?

## External-research determination

External sources are not necessary. The problem is an internal packaging and source-repository architecture conflict fully established by the current repository files and the user's explicit requirement.

## Source-derived notes

Not applicable. `links.md` records that no external source was needed. Repository inspection establishes that a source repository can dogfood its product without storing source-repository state inside the product template by using a separate live instance whose configuration points to the shared templates and schemas.

## Inferences and uncertainty

- The bundled scripts should accept an explicit instance root so the normal `.tasks/` installation and the source repository's `.project-tasks/` installation use identical logic.
- The generic template should be validated differently from a live instance because required placeholders are intentional before installation.

## Research conclusion

Repository evidence establishes the need for separate pristine-template and live-instance validation modes. The final implementation direction is selected in `findings.md`, not here.
