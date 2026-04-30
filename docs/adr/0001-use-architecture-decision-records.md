# ADR-0001: Use Architecture Decision Records

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Process / Workflow |
| Deciders | Project maintainers |
| Consulted | Existing planning artifacts |
| Informed | Future contributors |
| Supersedes |  |
| Superseded by |  |
| Related |  |

## Context

Argus already contains substantial architectural rationale in `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, research notes, roadmap files, README prose, and commit history. That rationale is valuable but scattered, time-bound, and mixed with execution plans. New contributors need a durable way to understand which decisions are load-bearing, why they were made, and what trade-offs were accepted.

## Options Considered

1. **Architecture Decision Records** — one immutable decision record per significant architectural choice.
2. **Keep rationale in planning docs** — continue recording decisions in GSD phase and milestone documents.
3. **Status quo / do nothing** — rely on README prose, code, and git history.

## Decision

**In the context of** a fast-moving robotics research codebase with many cross-cutting decisions, **facing** scattered rationale and future maintenance risk, **we decided for** Architecture Decision Records under `docs/adr/` **to achieve** explicit decision history and governance, **accepting** the overhead of maintaining ADRs for significant changes.

## Rationale

ADRs make architectural memory reviewable, searchable, and separate from temporary execution plans. Planning docs explain what was being built during a phase; ADRs explain why the resulting constraints should continue to shape future work.

## Consequences

### Positive

- Future architecture changes have a canonical place to record rationale and consequences.
- Accepted decisions can be audited against the codebase.
- README and planning docs can stay focused on usage and execution without carrying all historical context.

### Negative

- Contributors must update ADRs when making significant architectural changes.
- Poorly written ADRs can become another stale documentation layer if not kept honest.

### Neutral / Follow-up

- `docs/adr/README.md` defines lifecycle states and transition rules.
- `docs/ARCHITECTURE.md` should reference ADRs for the reasons behind the current shape.

## References

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/STACK.md`
- `.planning/research/PITFALLS.md`
