# Phase 3: frontend-picker-and-ui - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 03-frontend-picker-and-ui
**Areas discussed:** Component architecture, Capability badges, Lifter dropdown UX, Restart overlay + ConfirmModal scope

---

## Component Architecture

### Q: How should detector UI components relate to existing SLAM components?

| Option | Description | Selected |
|--------|-------------|----------|
| Clone + rename | Duplicate AlgorithmDropdown/Section/ParameterPanel/RestartOverlay as Detector* variants. ~450 lines dup; zero SLAM risk. | ✓ |
| Generic refactor w/ store prop | Rewrite as `BackendDropdown<T>` etc.; one codebase, higher SLAM regression risk. | |
| Shared primitives + thin wrappers | Middle ground; extract shared list-item / pill primitives. | |

**User's choice:** Clone + rename
**Notes:** Preserves v2.0 SLAM UX; divergence later (detector-specific params) costs nothing; simpler mental model per component.

---

### Q: DET-UI-06 — how do we verify detectorStore shape mirrors slamStore?

| Option | Description | Selected |
|--------|-------------|----------|
| TypeScript structural equivalence test | Vitest + type helper / key diff; compile + runtime check. | ✓ |
| Vitest + @testing-library snapshot | Snapshot default state. Brittle. | |
| Inline comment, no test | Lowest rigor. | |

**User's choice:** TypeScript structural equivalence test
**Notes:** Catches drift at compile time; fast; no screenshot infra.

---

## Capability Badges

### Q: How should CapabilityBadge render heterogeneous detector capability values?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend CapabilityBadge to accept key+value | One component, `{label, value}` props; SLAM call sites adapt. | ✓ |
| New DetectorCapabilityBadge sibling | Zero SLAM risk; duplicates pill styling. | |
| Mode prop | Single component with `mode="slam"|"detector"`. Coupled. | |

**User's choice:** Extend CapabilityBadge to accept key+value
**Notes:** Pill styling shared; SLAM call site migrates with an adapter.

---

### Q: Which capability keys show as badges per DET-UI-01?

| Option | Description | Selected |
|--------|-------------|----------|
| framework + license + cpu_latency_hint_ms | Exact DET-UI-01 wording; 3 badges. | ✓ |
| All 5 mandatory keys | More info, visual clutter. | |
| Minimal: framework + license only | 2 badges. | |

**User's choice:** framework + license + cpu_latency_hint_ms
**Notes:** Matches DET-UI-01 requirement exactly; outputs_3d_natively is functional not visual.

---

## Lifter Dropdown

### Q: Where does the Lifter dropdown live in the Sidebar?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline inside DetectorSection | Below detector dropdown, above param panel; cohesive. | ✓ |
| Separate LIFTER section | Its own collapsible section. More chrome. | |
| Parameter panel accordion | Buried. | |

**User's choice:** Inline inside DetectorSection
**Notes:** Lifter is detector-dependent (hidden when outputs_3d_natively=true); grouping makes sense.

---

### Q: Does switching the Lifter trigger a restart?

| Option | Description | Selected |
|--------|-------------|----------|
| No restart — hot-swap via REST only | Faster, but diverges from detector flow. | |
| Restart on switch (mirror detector) | Full restart, ConfirmModal + overlay + pending_lifter. UX consistency. | ✓ |
| Hot-swap with confirmation modal | Confirm but no restart. | |

**User's choice:** Restart on switch (mirror detector)
**Notes:** UX consistency locked; ONE restart code path serves both detector and lifter switches.

---

### Q: Lifter REST routes — add in Phase 3 or defer?

| Option | Description | Selected |
|--------|-------------|----------|
| Add now | 4 routes in detector_routes.py; Phase 4 drops PointClusterLifter in via registry only. | ✓ |
| Defer to Phase 4 | Saves ~80 lines now; fragments the work. | |

**User's choice:** Add now
**Notes:** Cohesive API contract; Phase 4 just registers the new lifter.

---

## Restart Overlay + ConfirmModal

### Q: RestartOverlay — shared with SLAM or dedicated?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing RestartOverlay w/ subsystem prop | `subsystem: 'slam'|'detector'|'lifter'`, customized message. One component. | ✓ |
| Dedicated DetectorRestartOverlay + LifterRestartOverlay | Three overlays; clear ownership, duplication. | |
| One overlay + concurrent-aware message | List of active restarts. More UI. | |

**User's choice:** Extend existing RestartOverlay w/ subsystem prop
**Notes:** SLAM call site migrates trivially; concurrent restarts render as stacked overlays.

---

### Q: ConfirmModal — shared or dedicated?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing ConfirmModal | Already props-driven (heading, body, labels). Zero component work. | ✓ |
| Dedicated DetectorConfirmModal | Sibling; no benefit. | |

**User's choice:** Reuse existing ConfirmModal
**Notes:** Fully generic; pass detector-specific text from DetectorSection.

---

### Q: Overlay DOM mount location?

| Option | Description | Selected |
|--------|-------------|----------|
| Alongside SLAM overlay in main canvas | Same parent as SceneViewer/CameraStrip. Blurs same viewport. | ✓ |
| Scoped to CameraStrip only | Semantically accurate (detector affects cameras only); visually weird. | |

**User's choice:** Alongside SLAM overlay
**Notes:** Matches user mental model of "system busy, don't click."

---

## Claude's Discretion

- Exact typography/spacing inside DetectorSection
- Restart spinner color
- Param panel confidence-threshold default value
- 2D bbox overlay opacity/stroke width
- ConfirmModal body text wording (within the decided pattern)
- Which Vitest runner configuration to use

## Deferred Ideas

- Generic BackendSection<T> refactor — rejected explicitly
- Concurrent-restart aggregate message — Phase 7 pipeline-editor polish
- CrashToast for detector crashes — Phase 5 DET-MODELS-06
- Live detection metrics in DetectorSection — Phase 6 DET-METRICS-01
- Detector per-robot dispatch UI — Phase 8 DET-STRETCH-04
- RGB_TEXT_PROMPT text-prompt UI (OWLv2) — Phase 5 DET-MODELS-04
