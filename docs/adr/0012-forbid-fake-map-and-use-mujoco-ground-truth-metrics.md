# ADR-0012: Forbid Fake mAP and Use MuJoCo Ground-Truth Metrics

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Testing Strategy |
| Deciders | Project maintainers |
| Consulted | `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/research/PITFALLS.md` |
| Informed | Metrics, frontend, and evaluation contributors |
| Supersedes | Detection-quality reporting without committed labels or simulator ground truth |
| Superseded by |  |
| Related | ADR-0002, ADR-0003, ADR-0011 |

## Context

Detection papers often report mAP, but Argus scenes do not automatically provide committed labeled 2D detection datasets. Planning explicitly forbids rendering `mAP` in the UI unless a labeled evaluation set is committed. For simulation, MuJoCo body positions provide honest ground truth for center error and per-class recall when scene mappings exist.

## Options Considered

1. **Forbid fake mAP; use MuJoCo GT metrics** — report center error, per-class recall, jitter, freshness, and latency unless labeled eval data exists.
2. **Report mAP from pseudo-labels** — easy number, but circular and misleading.
3. **Report only detector FPS and confidence** — honest but insufficient for comparing geometric quality.
4. **Status quo / do nothing** — let each metrics panel choose labels independently.

## Decision

**In the context of** simulation-based perception with known scene state but no committed detection-label dataset, **facing** pressure to show standard detection metrics, **we decided to** forbid fake mAP and use MuJoCo ground-truth metrics where available **to achieve** honest backend comparison, **accepting** that some familiar benchmark numbers will be absent.

## Rationale

A misleading metric is worse than no metric. MuJoCo can provide body positions and orientations, which are directly relevant to 3D detection quality. mAP requires labels; if labels are not committed, the UI must not pretend otherwise.

## Consequences

### Positive

- Metrics reflect actual simulator truth rather than detector self-agreement.
- Backend comparisons can include geometric accuracy, freshness, and stability.
- The UI sets correct expectations about evaluation coverage.

### Negative

- Users expecting paper-style mAP may need explanation.
- Scene-to-class mappings must be maintained for ground-truth metrics.

### Neutral / Follow-up

- A future labeled evaluation set can re-enable mAP under an explicit flag.
- Metrics should distinguish live operational metrics from benchmark/evaluation metrics.

## References

- `.planning/REQUIREMENTS.md` — DET-METRICS-02 and DET-METRICS-03
- `.planning/PROJECT.md` — Honest metrics decision
- `.planning/research/PITFALLS.md` — MuJoCo has no detection ground truth / fake mAP pitfall
