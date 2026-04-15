---
phase: 6
slug: detection-metrics-and-mujoco-gt
status: approved
shadcn_initialized: false
preset: none
created: 2026-04-15
reviewed_at: 2026-04-15
---

# Phase 6 — UI Design Contract

> Visual and interaction contract for the detection metrics subsection of `MetricsPanel`. This phase EXTENDS an existing component (CONTEXT D-04); the contract's primary job is to lock design continuity with the current SLAM rows so executor-added rows are visually indistinguishable from pre-existing ones.

**Source of all visual tokens:** `frontend/src/components/MetricsPanel.tsx` (Phase v2.0 13-01, currently deployed). This document codifies what is already there + the minimal additive rules for the detection subsection.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (manual inline-styles, no shadcn, no Tailwind) |
| Preset | not applicable |
| Component library | none (custom React components, inline `style={{}}` props) |
| Icon library | Unicode geometric shapes (`\u25B2`, `\u25BC` for collapse; solid circle dot via `border-radius: 50%` div) — no npm icon dep added by this phase |
| Font | system default (no `font-family` set in `MetricsPanel`); monospace values via `fontFamily: 'monospace'` inline — matches OS monospace fallback chain |

**Rationale for "none":** The Argus frontend is a Vite + React SPA with per-component inline styles. No Tailwind, no shadcn, no CSS-in-JS framework. The existing `MetricsPanel` sets its own tokens inline; this phase reuses them verbatim. Introducing a component library for a 7-row additive change would be a scope explosion and would desync the new rows from the existing SLAM rows. Locked: inline-style continuation.

**Files touched by this phase (UI surface):**
- `frontend/src/components/MetricsPanel.tsx` — EXTEND (add detection subsection + section separator)
- `frontend/src/stores/metricsStore.ts` — EXTEND (add `detectionPerRobot` + `detectionHistory` slices; no UI impact)
- `frontend/src/utils/messageTypes.ts` — EXTEND (add `DetectionMetrics` + `DetectionMetricHistory` types; no UI impact)

No new component files. No new CSS files. No new icon/font assets.

---

## Spacing Scale

Declared values (all multiples of 4, all already in use in `MetricsPanel.tsx`):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tab-bar gap (`gap: '4px'`), delta-margin (`marginTop: '4px'`) |
| sm | 8px | Per-robot metric-row vertical gap (`gap: '8px'`), robot-header padding-left, section-separator internal padding |
| md | 12px | Panel-content outer padding (`padding: '12px'`), tab-bar bottom margin, section-separator top margin |
| lg | 24px | Per-robot column horizontal gap (`gap: '24px'`) |
| xl | 32px | Collapse-toggle button height (`height: '32px'`) |

Exceptions for this phase:
- **8px × 8px status dot** (`width/height: 8px`) — already present in SLAM; detection subsection does NOT introduce a new status-dot control.
- **3px left border** on per-robot column (`borderLeft: '3px solid ...'`) — already present; detection subsection inherits the same border from the enclosing per-robot column, does NOT paint its own.
- **1px top border** on panel root (`borderTop: '1px solid #2a2a4a'`) — already present; detection subsection reuses this exact hex for the section separator rule (below).
- **2px active-tab underline** (`borderBottom: '2px solid #2ecc71'`) — already present; detection subsection does NOT add new tabs.
- **minWidth 140px** on per-robot column — already present; detection subsection MUST NOT widen this (all new value labels must fit; measurement: worst-case `1500.0 ms` = 48px @ 13px monospace ≤ available column width after 60px label).

**Forbidden values** (would break continuity): `padding: '16px'`, `gap: '16px'`, any `px` value not in {4, 8, 12, 24, 32} within this panel.

---

## Typography

All sizes/weights below are already declared in `MetricsPanel.tsx`. Phase 6 MUST NOT introduce any new size or weight.

| Role | Size | Weight | Line Height | Used For |
|------|------|--------|-------------|----------|
| Caption (section label) | 10px | 600 | default (~1.4, browser default) | Section separator label (`DETECTION_METRICS`), "ICP baseline" footer note already in baseline tab |
| Label / hint | 11px | 400 | default | Empty-state hint text ("Start a session to see live SLAM metrics." already present) |
| Row label + robot header | 12px | 600 (robot header) / 400 (row label) | default | Metric-row left label (`#888`), robot column header (`#e0e0e0`), collapse bar, tab labels |
| Value (monospace) | 13px | 400 | default | Metric-row right value (`#e0e0e0` monospace) |

**Exactly 4 sizes:** 10, 11, 12, 13. Exactly 2 weights: 400 (regular) and 600 (semibold).

**Font families:**
- Default: system sans (no explicit `fontFamily` — browser default, typically San Francisco / Segoe UI / Roboto).
- Monospace: `fontFamily: 'monospace'` (OS monospace fallback — typically Menlo / Consolas / Courier New). ALL detection metric values MUST use `fontFamily: 'monospace'` to align numerically with existing ATE / RPE / ms/frame values.

**Letter-spacing / transform:**
- Section separator label uses `letterSpacing: '1px'` and `textTransform: 'uppercase'` (new — see Section Separator below). No other text in this panel uses transforms.

**Line height:**
- Relies entirely on browser default (not explicitly set anywhere in the panel). The panel is dense-metric UI, not prose — explicit `lineHeight` would introduce vertical drift between SLAM rows and detection rows. Locked: do NOT set `lineHeight` on any new element.

---

## Color

The panel is a dark-surface densemetric dashboard. Color roles below mirror the existing `MetricsPanel.tsx` palette — no new hex introduced by this phase except the optional section-separator label color (which reuses an existing `#666` already present in the baseline tab's "ICP baseline" footer).

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#111122` | Panel background (`background: '#111122'`) |
| Secondary (30%) | `#2a2a4a` | Panel top border rule; section separator rule (detection subsection); baseline delta borders (existing) |
| Text-primary | `#e0e0e0` | Metric values, robot header, status text |
| Text-secondary | `#888` | Metric row labels, collapse bar text, tab labels, empty-state body |
| Text-tertiary | `#666` | Empty-state hint, section-separator label ("DETECTION_METRICS"), baseline-info footer |
| Text-quaternary | `#555` | "ICP baseline" footer (already present; detection subsection does NOT use this tier) |
| Accent (10%) | `#2ecc71` (green) | ACTIVE tab underline + text; `ok` status dot; improvement delta (existing) |
| Warning | `#f1c40f` (amber) | `initializing` / `relocalizing` status dot; **freshness 1s < fresh ≤ 3s** (new, this phase) |
| Destructive / Critical | `#e74c3c` (red) | `lost` status dot; regression delta; **freshness > 3s** (new, this phase) |

**Accent reserved for (explicit list):**
1. Active `role="tab"` underline (`borderBottom: '2px solid #2ecc71'`) and text color.
2. `ok` tracking-status dot (`background: '#2ecc71'`).
3. Sparkline stroke in baseline tab (`color="#2ecc71"` on `<Sparkline>`).
4. "Improvement" delta percentage text color in baseline tab (negative delta — existing).

**Accent is NOT used for:**
- Any detection-subsection value label or row background (none get "highlighted").
- Any hover state, focus ring, or button border.
- Any count-like value (det/frame, queue) — these are neutral `#e0e0e0`.

**Warning/Destructive usage (new this phase — freshness traffic-light):**
Detection subsection's `fresh` row value text colorizes by staleness:
- `freshness ≤ 1.0s` → `#e0e0e0` (normal text-primary — healthy)
- `1.0s < freshness ≤ 3.0s` → `#f1c40f` (warning)
- `freshness > 3.0s` → `#e74c3c` (destructive)

Rationale: freshness is the single detection metric where user action is implied (a stale detection stream means the backend is stuck). Other metrics (p50/p95, conf, queue, jitter) render in neutral `#e0e0e0` regardless of magnitude — we deliberately do not colorize "bad" p95 because what counts as bad is backend-dependent (YOLO 50ms vs BoxeR 15000ms). Let the human read the number.

**60/30/10 check:**
- 60% dominant `#111122` — panel surface (majority of pixels).
- 30% secondary `#2a2a4a` + neutral text palette (`#e0e0e0` / `#888` / `#666`) — all structural chrome.
- 10% accent `#2ecc71` + semantic warning/destructive — reserved for the four bulleted uses above + the freshness traffic-light. No accent bleed into metric rows, borders, or icon fills.

**Per-robot column left border** uses `robotColor(index)` from `frontend/src/utils/palette.ts` (Okabe-Ito 8-color colorblind-safe palette). This is the EXISTING SLAM column border — the detection subsection inherits it (same column, border paints the whole column). CONTEXT D-07 locks: no per-class palette, no per-metric palette.

---

## Layout & Composition

### Section Separator (new this phase)

Between the existing SLAM rows (`ATE / RPE / ms/frame / Status`) and the new detection rows (`infer p50 / infer p95 / det/frame / conf / queue / fresh / jitter`), insert one separator per per-robot column:

```jsx
<div style={{
  marginTop: '12px',
  marginBottom: '8px',
  paddingTop: '8px',
  borderTop: '1px solid #2a2a4a',
  fontSize: '10px',
  fontWeight: 600,
  letterSpacing: '1px',
  textTransform: 'uppercase',
  color: '#666',
}}>
  detection
</div>
```

**Label text:** `detection` (lowercase in source; rendered UPPERCASE via `textTransform`). ASCII-only — no underscore, no emoji. The label `DETECTION` at 10px / #666 is visually subordinate to the robot-id header at 12px / #e0e0e0 / 600, making the column hierarchy: Robot Header → SLAM rows → Separator → Detection rows.

**Why not `DETECTION_METRICS`** as shown in the prompt's first-draft suggestion: the word "metrics" is redundant inside a panel already labeled "Metrics" (see collapse bar `▲ Metrics`). `DETECTION` alone is shorter, fits column width at 140px minWidth, and is unambiguous in context.

**Placement:** Inside the per-robot column div, after the status row's closing `</div>` and before the detection row stack opens. One separator per robot column (NOT a single horizontal rule across the panel — that would break the column-based layout).

### Detection Rows (new this phase)

Seven rows per robot column, in this exact order, using identical row markup to the existing SLAM rows:

```jsx
<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
  <span style={{ fontSize: '12px', color: '#888' }}>{label}</span>
  <span style={{ fontSize: '13px', fontFamily: 'monospace', color: {valueColor} }}>
    {formattedValue}
  </span>
</div>
```

Row stack: `display: 'flex', flexDirection: 'column', gap: '8px'` (identical to existing SLAM row stack). The separator `<div>` sits OUTSIDE this stack but inside the per-robot column.

**The 7 rows (label, source, format, color):**

| Order | Label | Source (store field) | Format | Value Color |
|-------|-------|----------------------|--------|-------------|
| 1 | `infer p50` | `detectionPerRobot[rid].inference_ms_p50` | `{v.toFixed(1)} ms` | `#e0e0e0` |
| 2 | `infer p95` | `detectionPerRobot[rid].inference_ms_p95` | `{v.toFixed(1)} ms` | `#e0e0e0` |
| 3 | `det/frame` | `detectionPerRobot[rid].detections_per_frame` | `{v}` (integer, no unit) | `#e0e0e0` |
| 4 | `conf` | `detectionPerRobot[rid].mean_confidence` | `{(v*100).toFixed(0)}%` | `#e0e0e0` |
| 5 | `queue` | `detectionPerRobot[rid].queue_depth` | `{v}` (integer; 0 or 1) | `#e0e0e0` |
| 6 | `fresh` | `detectionPerRobot[rid].freshness_s` | `{v.toFixed(2)}s` | traffic-light (see Color) |
| 7 | `jitter` | `detectionPerRobot[rid].jitter_m` | `{v.toFixed(3)}m` | `#e0e0e0` |

**Confidence format decision** (prompt asked us to pick one): **percentage** `{(v*100).toFixed(0)}%`. Justification:
1. Human-readable at a glance — `87%` parses instantly; `0.87` requires mental conversion to a familiar scale.
2. Matches the delta format already used in baseline tab (`+12%`, `-5%`) — percent is the established "ratio" presentation language in this panel.
3. Integer percent (0 decimals) keeps column width narrow; `87%` = 3 chars vs `0.87` = 4 chars.
4. The underlying precision (two sig figs after multiplication, rounded) is sufficient — nobody cares if mean confidence is 0.871 vs 0.874.

**Unit-suffix convention** (locked):
- `ms` has a space before: `12.3 ms` — matches human typographic convention for SI units with symbols.
- `s`, `m`, `%` have NO space: `1.25s`, `0.152m`, `87%` — matches existing SLAM `0.042m` (ATE) formatting in the same panel. Consistency with SLAM is the overriding constraint.
- Integer values (det/frame, queue) have NO suffix — unit is implied by the label.

**Rationale for the SLAM→detection row order divergence** (SLAM = `ATE/RPE/ms-per-frame/Status`; detection = `p50/p95/det-per-frame/conf/queue/fresh/jitter`): detection has no "status" equivalent (there's no tracking state machine for a detector). `queue` is the closest analog (worker backpressure indicator) but it's a count, not a categorical state — hence no status dot. The ordering groups semantically: latency (p50, p95), throughput (det/frame, conf), health (queue, fresh), geometry quality (jitter).

### Empty-State Handling

Three distinct empty-state cases (CONTEXT D-01, D-02 + prompt guidance):

**Case A — No robots at all (panel-level empty).**
Existing SLAM path: renders "No metrics yet" + "Start a session to see live SLAM metrics." hint at 13px/#888 + 11px/#666. The detection subsection is NOT rendered in this case (the `robotIds.length === 0` guard wraps the whole Live view). NO detection-specific empty copy needed — the panel-level empty already owns this case.

**Case B — Robots exist, but `detectionPerRobot[rid]` is undefined (pre-warmup, backend hasn't emitted yet).**
Render all 7 detection rows with value = `--` at `#888` (matching the SLAM baseline-tab fallback `return '--'` pattern already in source). DO NOT fallback to `0` / `0.0 ms` — that would misrepresent "no data yet" as "measured zero latency". The separator label `DETECTION` renders regardless (presence indicates the section exists).

**Case C — `detectionPerRobot[rid]` defined but `queue_depth == 0` AND no `latest`.**
Render last-known values (don't revert to `--`). The tracker already holds the previous frame's data; freshness will tick upward, colorizing amber then red via the traffic-light rule. The user learns staleness from `fresh`, not from disappearing numbers. This is the intended signaling design.

**Empty-state value formatter (single source of truth):**
```typescript
function formatMetric(v: number | null | undefined, formatter: (x: number) => string): {text: string; color: string} {
  if (v == null) return { text: '--', color: '#888' };
  return { text: formatter(v), color: '#e0e0e0' };
}
```
Applied uniformly across all 7 rows. The `fresh` row wraps this with the traffic-light override when value is non-null.

### Collapse / View-Mode Behavior

- The existing collapse toggle (`▲ Metrics` / `▼ Metrics`) controls the entire panel. CONTEXT D-04 locks: NO additional collapse granularity. Detection subsection follows SLAM's collapse state.
- Existing tabs (`Live`, `vs Baseline`) remain unchanged. CONTEXT D-05 locks: detection metrics appear ONLY in the `Live` tab. The `vs Baseline` tab continues to show SLAM-only content.
- No new keyboard shortcuts, no new hover affordances, no tooltips (the row labels are self-explanatory; adding tooltips here would introduce a tooltip pattern this panel doesn't otherwise have).

### Horizontal Overflow

The existing Live view wraps per-robot columns in `display: 'flex', gap: '24px', overflowX: 'auto'`. Adding 7 rows per column INCREASES column height from ~4 rows × 20px ≈ 80px to ~11 rows + separator ≈ 220px. This is a vertical growth, NOT horizontal. Horizontal overflow scrolling behavior is unchanged (many-robot sessions still scroll horizontally; each column is wider than the viewport's fair share).

**Panel total height (expanded, per robot 4+7 rows + separator + header):**
- Collapse bar: 32px
- Tab bar: ~30px + 12px margin-bottom
- Robot header: 12px + 8px margin-bottom
- SLAM rows (4): 4×~20px + 3×8px gap ≈ 104px
- Separator: 12px marginTop + 1px border + 8px paddingTop + ~12px label + 8px marginBottom ≈ 41px
- Detection rows (7): 7×~20px + 6×8px gap ≈ 188px
- Outer padding 12px top + bottom

Total ≈ 420px when expanded. No scroll constraint on the panel (it's already at `position` fixed bottom in the app layout; the viewport accommodates).

---

## Copywriting Contract

No new CTAs are introduced by this phase (panel is read-only dashboard, no buttons beyond the existing collapse toggle + tab switcher, no destructive actions).

| Element | Copy |
|---------|------|
| Primary CTA | not applicable (no buttons introduced by Phase 6; existing `▲ Metrics` / `▼ Metrics` toggle copy is NOT changed) |
| Section-separator label | `detection` (source; rendered `DETECTION` via CSS uppercase) |
| Row label — inference p50 | `infer p50` |
| Row label — inference p95 | `infer p95` |
| Row label — detections per frame | `det/frame` |
| Row label — mean confidence | `conf` |
| Row label — queue depth | `queue` |
| Row label — freshness | `fresh` |
| Row label — 3D center jitter | `jitter` |
| Empty-state value placeholder | `--` (two hyphens; matches existing SLAM baseline-tab pattern) |
| Empty state heading (panel-level, unchanged) | `No metrics yet` (existing — not modified by this phase) |
| Empty state body (panel-level, unchanged) | `Start a session to see live SLAM metrics.` (existing — not modified; NOTE: intentionally retains "SLAM" wording because the panel-level empty state fires when NO data at all exists, which is a session-not-started case, not a detector-not-ready case) |
| Error state | not applicable — the panel has no error surface; backend errors surface via the existing `CrashToast` + `RestartOverlay` patterns owned by other components |
| Destructive confirmation | not applicable — no destructive actions in this phase |

**Forbidden strings in UI** (DET-METRICS-03, SC#3, CONTEXT D-10 — grep-enforced):
- `mAP` (case-sensitive)
- `map_50`
- `map_75`
- `mean_average_precision`

None of the above may appear in any row label, section label, tooltip, placeholder, or payload-derived string rendered in the DOM. The grep test `tests/contract/test_no_map_in_ui.py` locks this.

**Copywriting rules applied:**
1. **Lowercase row labels** — matches existing SLAM rows (`ATE`, `RPE`, `ms/frame`, `Status`). All-caps would visually dominate at 12px in a dense layout. The outlier is SLAM's `ATE`/`RPE` being initialisms (naturally uppercase); detection metrics have no such initialisms in English, so they stay lowercase.
2. **Abbreviations over full words** — `conf` not `confidence`, `fresh` not `freshness`, `queue` not `queue depth`. Column width is 140px minWidth with value on the right; 10-char label at 12px ≈ 60px, leaving 60px for the value. Full words would push values past the right edge.
3. **No punctuation in labels** — `det/frame` uses `/` as an inline unit-per-unit separator (matches SLAM's `ms/frame`). No colons, no parens, no em-dashes. Values stay visually clean.
4. **Consistent verb-free naming** — none of the labels start with a verb. They are snapshot nouns describing current values, not imperative instructions.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable — shadcn not initialized |
| third-party | none | not applicable |

This phase introduces no third-party UI packages, no registry blocks, no npm design-system deps. All markup is inline-styled JSX added to an existing file. Registry safety gate: not required.

---

## Interaction Accessibility

Locked minimums (all already met by the existing panel; detection subsection inherits):

- **Color contrast:** Text-primary `#e0e0e0` on dominant `#111122` = 13.5:1 (WCAG AAA for all text sizes). Text-secondary `#888` on dominant `#111122` = 4.7:1 (WCAG AA for normal text). Section-separator `#666` on dominant `#111122` = 3.1:1 (fails WCAG AA for normal text but label is 10px, bold, all-caps, letter-spaced — categorized as "large/presentational" and acceptable for a caption; if a11y audit later flags this, promote to `#888`).
- **Focus rings:** No interactive element is introduced by this phase. Existing collapse button and tab buttons retain their default browser focus rings (no custom override).
- **Semantic roles:** The detection subsection is purely presentational (value rows). No `role="list"` or `role="table"` added — flex-column divs match the existing SLAM row treatment. The tab container already uses `role="tablist"` + `role="tab"` + `aria-selected` correctly; detection subsection lives inside the active `Live` tab panel with no a11y changes.
- **Live region updates:** NOT added. Screen readers would be overwhelmed by 30Hz metric updates across 2+ robots. The panel is an at-a-glance visual dashboard for sighted operators; screen-reader users interact with the JSONL export endpoint (which is machine-parseable). This is consistent with the existing SLAM rows' treatment.
- **Reduced motion:** No animations introduced by this phase.

---

## Consumer Guidance

**For gsd-planner:**
- Design tokens are frozen in the "Spacing / Typography / Color" sections above. Any plan-task that adds a new size, weight, or hex must be rejected or escalated as a CONTEXT amendment.
- The 7-row list in "Detection Rows" is the authoritative UI inventory — no plan should add an 8th row (e.g., `drops` or `first_inference_ms`) without explicit CONTEXT reopen.
- The `formatMetric` helper (empty-state formatter) is a planner-level primitive — recommend a dedicated utility in `frontend/src/components/MetricsPanel.tsx` scope (not a new file) to keep the diff localized.

**For gsd-executor:**
- COPY ROW MARKUP VERBATIM from the existing SLAM ATE row (`MetricsPanel.tsx:130-135`). Same outer `div` flex props, same inner `span` styles. The only allowed deltas are label text, source field, formatter, and value color (for `fresh` only).
- Separator `<div>` renders ONCE PER PER-ROBOT COLUMN, positioned between the status row and the first detection row. NOT a panel-wide horizontal rule.
- When `detectionPerRobot[rid]` is `undefined`, render all 7 rows with `--` / `#888`. Do NOT hide the rows (the empty rows communicate "detector not yet reporting"; hidden rows communicate "no detector running").
- The `fresh` traffic-light is the ONLY colorized value in the detection subsection. All other values are `#e0e0e0`.

**For gsd-ui-auditor:**
- Visual-diff check: existing SLAM rows and new detection rows MUST be visually indistinguishable at the row level (same typography, same label color, same value color outside of `fresh`, same vertical gap). If an auditor screenshots both sections and the rows look like they belong to different components, the contract was violated.
- Copywriting check: grep output of `mAP|map_50|map_75|mean_average_precision` against the rendered DOM (or against `frontend/src/**/*.{ts,tsx}` per D-10) must be empty.
- Separator check: there is exactly ONE `DETECTION` separator per visible robot column when the Live tab is active AND robots exist. Zero separators in baseline tab, zero separators when panel is collapsed, zero separators in empty state.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

## Amendment 2026-04-15 — SC#2 Row Additions (err m, recall)

**Context:** Revision checker found that SC#2 deliverables (`center_error_m`, `per_class_recall`) were absent from the 7-row detection inventory locked above. Plans 04/08/10/11 were returning tracker state, payload surfacing, coordinator pump consumption, and store slices — but the UI had no rows to render them. This amendment extends the row inventory from 7 to 9 without reopening the broader UI-SPEC.

**Scope of amendment (strictly additive):**

- Row count: 7 → **9**.
- Append order: after `jitter`, render `err m`, then `recall`.
- All other UI-SPEC decisions (tokens, spacing, typography, palette, interaction, accessibility, registry safety) remain unchanged.

### New Row Inventory (rows 8–9)

| # | Label     | Source (store)                          | Format          | Empty-State | Color    |
|---|-----------|-----------------------------------------|-----------------|-------------|----------|
| 8 | `err m`   | aggregate mean of `center_error_m` across `detectionGtPerRobot[rid][class].center_error_m` (excluding `null`) | `${v.toFixed(3)} m` (space before `m` — matches SLAM `m` convention) | `--` at `#888` when `detectionGtPerRobot[rid]` is undefined OR all classes have `center_error_m === null` | Neutral `#e0e0e0` always |
| 9 | `recall`  | aggregate mean of `per_class_recall` across `detectionGtPerRobot[rid][class].per_class_recall` | `${(v * 100).toFixed(0)}%` (no space before `%` — matches `conf` convention) | `--` at `#888` when `detectionGtPerRobot[rid]` is undefined OR has no classes | Neutral `#e0e0e0` always |

### Copywriting Rules (extend §Copywriting)

- **`err m` label** → pipes through `center_error_m` aggregate. Unit suffix `" m"` (leading space matches SLAM ATE convention in the existing spec).
- **`recall` label** → pipes through `per_class_recall` aggregate. Unit `"%"` (no leading space matches `conf` convention in the existing spec).
- **Empty-state:** Both rows emit `--` rendered at `#888` when there is no aggregate value to show (no GT classes mapped OR no classes with a non-null center_error).

### Color Rules (extend §Color Role)

- **Both rows use the neutral value color `#e0e0e0`.** NO traffic-light gradient. Rationale: SC#2 literal specification is "report the number as-is"; any threshold would be a planner-injected judgement not sanctioned by CONTEXT. The operator reads the raw scalar and decides what's acceptable.

### Aggregation Rules

- **Simple mean across mapped classes per robot.** No weighting by sample count. Classes with `center_error_m: null` are excluded from the `err m` numerator (but NOT from the `recall` numerator — recall has a defined 0.0 default per Plan 04).
- Aggregation is a UI-level concern; the store holds the full per-class breakdown so later phases can expose a class-drill-down without touching the store schema.

### Planner / Executor / Auditor Guidance

- **For gsd-planner:** The 9-row inventory is the new lock. Any future addition requires a further amendment. Deferred sparkline history for err_m / recall remains deferred (D-06).
- **For gsd-executor:** Copy the row markup verbatim from the existing SLAM ATE row (unchanged from the pre-amendment spec). The new rows differ only in label text, source field, formatter, and NO color override (unlike `fresh`). Do NOT introduce per-class drill-down in this phase.
- **For gsd-ui-auditor:** 9 row labels per robot column under Live tab. Two of them (`err m`, `recall`) render `--` / `#888` when no GT mapping is active — this is expected behavior, not a bug.

### Dimension Sign-Off Deltas

- Copywriting: 2 new row labels + 2 new copywriting rules → re-verify PASS after amendment.
- Color: new rows use existing `#e0e0e0` / `#888` tokens only → no palette change.
- Typography: new rows use existing 12px label / 13px mono value → no change.
- Spacing: inherits the 8px vertical gap of the row stack → no change.
- Registry Safety: unchanged.
- Accessibility: unchanged (same inline-style presentational pattern as rows 1–7).

