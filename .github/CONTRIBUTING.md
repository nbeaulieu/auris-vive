# Contributing

This repo contains two kinds of work — design/brand and engineering. Both follow different conventions. Read the relevant section before opening a PR.

---

## For designers and artists

### Adding or updating brand files

Brand files live in `brand/`. The key principle: **this directory should be navigable by someone who has never written code.**

- `identity.html` is a standalone browser file. Keep all assets inlined. Do not add external dependencies beyond the two Google Fonts already loaded.
- Markdown files (`palette.md`, `typography.md`, `voice.md`) should use plain language. Avoid CSS variable names and code snippets except in clearly labelled code blocks.
- When you update a design decision, update the corresponding open question in `engineering/design/SDD-001-pipeline-overview.html` and close it.
- Open design questions live in `brand/README.md`. When one is resolved, move it to the relevant spec file and remove it from the list.

### Naming conventions

- Brand files use lowercase kebab-case: `palette.md`, `voice.md`
- Assets use descriptive names: `logo-dark.svg`, `logo-light.svg`, `wordmark-horizontal.svg`

---

## For engineers

### Adding an Architecture Decision Record (ADR)

ADRs live in `engineering/decisions/`. They are numbered sequentially.

**File naming:** `ADR-XXX-short-description.md`

**Template:**

```markdown
# ADR-XXX — Short title

| Field      | Value       |
|------------|-------------|
| Status     | Proposed / Accepted / Deprecated |
| Date       | YYYY-MM-DD  |
| Deciders   | Names or team |
| Relates to | Other ADR or SDD numbers |

## Context and problem statement
## Decision drivers
## Considered options
## Decision
## Consequences
## References
```

Rules:
- Every rejected option must have a documented reason for rejection
- Accepted ADRs are immutable — if you change your mind, write a new ADR that supersedes the old one and mark the old one `Deprecated`
- Link the new ADR from the engineering `README.md` table

### Adding a Stage Design Document (SDD)

SDDs live in `engineering/design/`. They are numbered sequentially.

**File naming:** `SDD-XXX-stage-name.md` (or `.html` for documents with embedded diagrams)

**Each SDD must include:**
1. Purpose and scope
2. Context — where this stage sits in the pipeline
3. Input contract (exact type, shape, constraints)
4. Output contract (exact type, shape, constraints)
5. Implementation (full annotated code)
6. Error handling (error taxonomy table)
7. Testing requirements (test case table)
8. Open questions (anything unresolved)

**Open questions** in an SDD should also be added to the registry in `SDD-001-pipeline-overview.html`.

### Resolving an open question

1. Write or update the relevant ADR
2. Update the SDD section that the question lived in
3. Remove the question from the open questions registry in `SDD-001`
4. Update the ADR table in `engineering/README.md`

---

## PR conventions

**Branch naming:**
- `brand/description` — brand and design changes
- `engineering/description` — pipeline and architecture changes
- `docs/description` — documentation-only changes

**PR titles:**
- `[Brand] Update palette — add stem colours`
- `[ADR] ADR-003 drum stem approach`
- `[SDD] SDD-003 separate stage first draft`

**Every PR needs:**
- A one-sentence description of what changed and why
- A reference to the open question it resolves (if applicable)

---

## Questions

- Brand and design → open an issue tagged `brand`
- Pipeline engineering → open an issue tagged `engineering`
- Something that spans both → open an issue tagged `product`
